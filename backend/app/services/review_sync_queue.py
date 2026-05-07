from __future__ import annotations

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SyncJob, TaskSchedule
from app.schemas import ReviewSyncRequest
from app.services.task_logs import add_task_log


async def enqueue_review_sync_job(
    session: AsyncSession,
    background_tasks: BackgroundTasks,
    request: ReviewSyncRequest,
    runner,
) -> SyncJob:
    schedule_name: str | None = None
    if request.schedule_id is not None:
        schedule = await session.get(TaskSchedule, request.schedule_id)
        if schedule is None or schedule.task_type != "steam_review_sync":
            raise HTTPException(status_code=404, detail="Task schedule not found")
        schedule_name = schedule.name

    sync_job = SyncJob(
        schedule_id=request.schedule_id,
        schedule_name=schedule_name,
        trigger_type="manual",
        app_id=request.app_id,
        job_type="steam_review_sync",
        source_type="steam_api",
        status="pending",
        requested_limit=request.limit,
    )
    session.add(sync_job)
    await session.commit()
    await session.refresh(sync_job)
    await add_task_log(
        session,
        sync_job.id,
        "任务已进入队列",
        details={
            "app_id": request.app_id,
            "schedule_id": request.schedule_id,
            "schedule_name": schedule_name,
            "trigger_type": "manual",
        },
    )
    await session.commit()
    background_tasks.add_task(runner, sync_job.id, request)
    return sync_job
