from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_session
from app.core.security import RequireOperator
from app.models import SyncJob, TaskSchedule
from app.schemas import (
    ReviewSyncRequest,
    SyncJobListItem,
    TaskScheduleResponse,
    TaskScheduleUpdate,
)
from app.services.review_sync import ReviewSyncOptions, SteamReviewSyncService

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
        except Exception:
            return
