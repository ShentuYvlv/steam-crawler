from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from src.utils.task_control import SteamTemporarilyUnavailableError, TaskCancelledError

from app.core.database import AsyncSessionLocal
from app.models import SyncJob, TaskSchedule
from app.services.review_sync import ReviewSyncOptions, SteamReviewSyncService
from app.services.steam_probe_gate import wait_for_steam_availability
from app.services.task_runtime import (
    finalize_cancelled_task,
    get_steam_sync_lock,
    register_cancel_event,
    unregister_cancel_event,
)

CHINA_TZ = ZoneInfo("Asia/Shanghai")


class TaskScheduler:
    def __init__(self, poll_interval_seconds: int = 60) -> None:
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.run_once()
            except Exception:
                pass

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.poll_interval_seconds,
                )
            except TimeoutError:
                continue

    async def run_once(self) -> None:
        now = datetime.now(tz=CHINA_TZ)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(TaskSchedule).where(
                    TaskSchedule.task_type == "steam_review_sync",
                    TaskSchedule.is_enabled.is_(True),
                    TaskSchedule.app_id.is_not(None),
                )
            )
            schedules = list(result.scalars().all())

            for schedule in schedules:
                if schedule.app_id is None:
                    continue
                if not await self._is_due(session, schedule, now):
                    continue
                if await self._has_running_job(session, schedule.id):
                    continue

                sync_job = SyncJob(
                    schedule_id=schedule.id,
                    schedule_name=schedule.name,
                    trigger_type="scheduled",
                    app_id=schedule.app_id,
                    job_type="steam_review_sync",
                    source_type="steam_api",
                    status="pending",
                    requested_limit=None,
                )
                session.add(sync_job)
                await session.commit()
                await session.refresh(sync_job)

                cancel_event = register_cancel_event(sync_job.id)
                try:
                    async with get_steam_sync_lock():
                        while True:
                            await session.refresh(sync_job)
                            if sync_job.status == "cancelled":
                                break
                            if sync_job.status == "cancel_requested":
                                await finalize_cancelled_task(
                                    session,
                                    sync_job,
                                    message="任务已取消",
                                    details={"reason": "cancel_requested_while_waiting"},
                                )
                                await session.commit()
                                break
                            try:
                                await wait_for_steam_availability(
                                    session,
                                    sync_job,
                                    cancel_event=cancel_event,
                                )
                            except TaskCancelledError:
                                await session.refresh(sync_job)
                                await finalize_cancelled_task(
                                    session,
                                    sync_job,
                                    message="任务已取消",
                                    details={"reason": "cancelled_during_probe_wait"},
                                )
                                await session.commit()
                                break

                            service = SteamReviewSyncService(session, cancel_event=cancel_event)
                            try:
                                result = await service.sync_reviews(
                                    ReviewSyncOptions(
                                        app_id=schedule.app_id,
                                        schedule_id=schedule.id,
                                        schedule_name=schedule.name,
                                        trigger_type="scheduled",
                                        limit=None,
                                        language=str(
                                            (schedule.options or {}).get("language") or "schinese"
                                        ),
                                        filter=str(
                                            (schedule.options or {}).get("filter") or "recent"
                                        ),
                                        review_type=str(
                                            (schedule.options or {}).get("review_type") or "all"
                                        ),
                                        purchase_type=str(
                                            (schedule.options or {}).get("purchase_type") or "all"
                                        ),
                                        use_review_quality=bool(
                                            (schedule.options or {}).get(
                                                "use_review_quality", True
                                            )
                                        ),
                                        per_page=int(
                                            (schedule.options or {}).get("per_page") or 100
                                        ),
                                        sync_job_id=sync_job.id,
                                    )
                                )
                            except SteamTemporarilyUnavailableError:
                                continue
                            if result.status in {"success", "partial_success", "cancelled"}:
                                break
                finally:
                    unregister_cancel_event(sync_job.id)

    async def _has_running_job(self, session, schedule_id: int) -> bool:
        result = await session.execute(
            select(SyncJob.id)
            .where(
                SyncJob.schedule_id == schedule_id,
                SyncJob.job_type == "steam_review_sync",
                SyncJob.status.in_(("pending", "waiting", "running", "cancel_requested")),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _is_due(self, session, schedule: TaskSchedule, now: datetime) -> bool:
        if schedule.app_id is None:
            return False

        result = await session.execute(
            select(SyncJob)
            .where(
                SyncJob.schedule_id == schedule.id,
                SyncJob.job_type == "steam_review_sync",
                SyncJob.status.in_(("success", "failed", "partial_success", "cancelled")),
            )
            .order_by(desc(SyncJob.started_at), desc(SyncJob.created_at), desc(SyncJob.id))
            .limit(1)
        )
        last_job = result.scalar_one_or_none()
        last_run_at = normalize_datetime(
            last_job.started_at if last_job and last_job.started_at else None
        )

        hour = schedule.hour if schedule.hour is not None else 0
        due_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if now < due_time:
            due_time -= timedelta(days=1)
        return last_run_at is None or last_run_at < due_time


def normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=CHINA_TZ)
    return value.astimezone(CHINA_TZ)
