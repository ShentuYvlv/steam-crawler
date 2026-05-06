from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal, get_session
from app.core.security import RequireOperator
from app.models import SyncJob, TaskLog, TaskSchedule
from app.schemas import (
    ReviewSyncRequest,
    SyncJobListItem,
    SyncJobWithLogsResponse,
    TaskLogResponse,
    TaskScheduleResponse,
    TaskScheduleUpdate,
)
from app.services.review_sync import ReviewSyncOptions, SteamReviewSyncService
from app.services.task_logs import add_task_log

router = APIRouter(prefix="/tasks", tags=["tasks"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[SyncJobListItem])
async def list_tasks(
    session: SessionDependency,
    limit: int = Query(default=50, gt=0, le=200),
) -> list[SyncJob]:
    result = await session.execute(
        select(SyncJob).order_by(desc(SyncJob.created_at), desc(SyncJob.id)).limit(limit)
    )
    return list(result.scalars().all())


@router.post("/reviews-sync", response_model=SyncJobListItem, status_code=202)
async def enqueue_reviews_sync(
    request: ReviewSyncRequest,
    background_tasks: BackgroundTasks,
    session: SessionDependency,
    current_user: RequireOperator,
) -> SyncJob:
    sync_job = SyncJob(
        app_id=request.app_id,
        job_type="steam_review_sync",
        source_type="steam_api",
        status="pending",
        requested_limit=request.limit,
    )
    session.add(sync_job)
    await session.commit()
    await session.refresh(sync_job)
    await add_task_log(session, sync_job.id, "任务已进入队列")
    await session.commit()
    background_tasks.add_task(_run_review_sync_job, sync_job.id, request)
    return sync_job


@router.patch("/schedule", response_model=TaskScheduleResponse)
async def update_reviews_sync_schedule(
    request: TaskScheduleUpdate,
    session: SessionDependency,
    current_user: RequireOperator,
) -> TaskSchedule:
    result = await session.execute(
        select(TaskSchedule).where(TaskSchedule.task_type == "steam_review_sync")
    )
    schedule = result.scalar_one_or_none()
    if schedule is None:
        schedule = TaskSchedule(task_type="steam_review_sync")
        session.add(schedule)

    schedule.is_enabled = request.is_enabled
    schedule.app_id = request.app_id
    schedule.interval = request.interval
    schedule.hour = request.hour
    schedule.minute = request.minute
    schedule.options = request.options
    await session.commit()
    await session.refresh(schedule)
    return schedule


@router.get("/schedule", response_model=TaskScheduleResponse | None)
async def get_reviews_sync_schedule(session: SessionDependency) -> TaskSchedule | None:
    result = await session.execute(
        select(TaskSchedule).where(TaskSchedule.task_type == "steam_review_sync")
    )
    return result.scalar_one_or_none()


@router.get("/{task_id}", response_model=SyncJobWithLogsResponse)
async def get_task_detail(task_id: int, session: SessionDependency) -> SyncJob:
    result = await session.execute(
        select(SyncJob).options(selectinload(SyncJob.logs)).where(SyncJob.id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{task_id}/logs", response_model=list[TaskLogResponse])
async def get_task_logs(task_id: int, session: SessionDependency) -> list[TaskLog]:
    result = await session.execute(
        select(TaskLog).where(TaskLog.task_id == task_id).order_by(TaskLog.created_at, TaskLog.id)
    )
    return list(result.scalars().all())


async def _run_review_sync_job(sync_job_id: int, request: ReviewSyncRequest) -> None:
    async with AsyncSessionLocal() as session:
        service = SteamReviewSyncService(session)
        try:
            await service.sync_reviews(
                ReviewSyncOptions(
                    app_id=request.app_id,
                    limit=request.limit,
                    language=request.language,
                    filter=request.filter,
                    review_type=request.review_type,
                    purchase_type=request.purchase_type,
                    use_review_quality=request.use_review_quality,
                    per_page=request.per_page,
                    sync_job_id=sync_job_id,
                )
            )
        except Exception as exc:
            task = await session.get(SyncJob, sync_job_id)
            if task is not None:
                task.status = "failed"
                task.error_message = str(exc)
                await add_task_log(
                    session,
                    sync_job_id,
                    "任务执行失败",
                    level="error",
                    details={"error": str(exc)},
                )
                await session.commit()
            return
