from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select

from app.core.database import AsyncSessionLocal
from app.models import SyncJob, TaskSchedule
from app.services.review_sync import ReviewSyncOptions, SteamReviewSyncService

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
                if await self._has_running_job(session, schedule.app_id):
                    continue

                sync_job = SyncJob(
                    app_id=schedule.app_id,
                    job_type="steam_review_sync",
                    source_type="steam_api",
                    status="pending",
                    requested_limit=None,
                )
                session.add(sync_job)
                await session.commit()
                await session.refresh(sync_job)

                service = SteamReviewSyncService(session)
                await service.sync_reviews(
                    ReviewSyncOptions(
                        app_id=schedule.app_id,
                        limit=None,
                        language=str((schedule.options or {}).get("language") or "schinese"),
                        filter=str((schedule.options or {}).get("filter") or "recent"),
                        review_type=str((schedule.options or {}).get("review_type") or "all"),
                        purchase_type=str((schedule.options or {}).get("purchase_type") or "all"),
                        use_review_quality=bool(
                            (schedule.options or {}).get("use_review_quality", True)
                        ),
                        per_page=int((schedule.options or {}).get("per_page") or 100),
                        sync_job_id=sync_job.id,
                    )
                )

    async def _has_running_job(self, session, app_id: int) -> bool:
        result = await session.execute(
            select(SyncJob.id)
            .where(
                SyncJob.app_id == app_id,
                SyncJob.job_type == "steam_review_sync",
                SyncJob.status.in_(("pending", "running")),
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
                SyncJob.app_id == schedule.app_id,
                SyncJob.job_type == "steam_review_sync",
                SyncJob.status.in_(("success", "failed")),
            )
            .order_by(desc(SyncJob.started_at), desc(SyncJob.created_at), desc(SyncJob.id))
            .limit(1)
        )
        last_job = result.scalar_one_or_none()
        last_run_at = normalize_datetime(
            last_job.started_at if last_job and last_job.started_at else None
        )

        minute = schedule.minute if schedule.minute is not None else 0
        hour = schedule.hour if schedule.hour is not None else 0

        if schedule.interval == "hourly":
            due_time = now.replace(minute=minute, second=0, microsecond=0)
            if now < due_time:
                due_time -= timedelta(hours=1)
            return last_run_at is None or last_run_at < due_time

        due_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now < due_time:
            due_time -= timedelta(days=1)
        return last_run_at is None or last_run_at < due_time


def normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=CHINA_TZ)
    return value.astimezone(CHINA_TZ)
