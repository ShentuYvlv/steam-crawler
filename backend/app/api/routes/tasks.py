from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal, get_session
from app.core.error_utils import format_exception_details, format_exception_message
from app.core.security import RequireOperator
from app.models import SyncJob, TaskLog, TaskSchedule
from app.schemas import (
    ReviewSyncRequest,
    SyncJobListItem,
    SyncJobWithLogsResponse,
    TaskLogResponse,
    TaskScheduleCreate,
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
    schedule_id: int | None = Query(default=None, gt=0),
) -> list[SyncJob]:
    statement = select(SyncJob)
    if schedule_id is not None:
        statement = statement.where(SyncJob.schedule_id == schedule_id)
    result = await session.execute(
        statement.order_by(desc(SyncJob.created_at), desc(SyncJob.id)).limit(limit)
    )
    return list(result.scalars().all())


@router.post("/reviews-sync", response_model=SyncJobListItem, status_code=202)
async def enqueue_reviews_sync(
    request: ReviewSyncRequest,
    background_tasks: BackgroundTasks,
    session: SessionDependency,
    current_user: RequireOperator,
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
    background_tasks.add_task(_run_review_sync_job, sync_job.id, request)
    return sync_job


@router.get("/schedules", response_model=list[TaskScheduleResponse])
async def list_task_schedules(session: SessionDependency) -> list[TaskSchedule]:
    result = await session.execute(
        select(TaskSchedule)
        .where(TaskSchedule.task_type == "steam_review_sync")
        .order_by(desc(TaskSchedule.is_enabled), TaskSchedule.app_id, TaskSchedule.id)
    )
    return list(result.scalars().all())


@router.post("/schedules", response_model=TaskScheduleResponse, status_code=201)
async def create_task_schedule(
    request: TaskScheduleCreate,
    session: SessionDependency,
    current_user: RequireOperator,
) -> TaskSchedule:
    schedule = TaskSchedule(
        name=request.name,
        task_type="steam_review_sync",
        is_enabled=request.is_enabled,
        app_id=request.app_id,
        interval="daily",
        hour=request.hour,
        minute=0,
        options=request.options,
    )
    session.add(schedule)
    await session.commit()
    await session.refresh(schedule)
    return schedule


@router.patch("/schedules/{schedule_id}", response_model=TaskScheduleResponse)
async def update_task_schedule(
    schedule_id: int,
    request: TaskScheduleUpdate,
    session: SessionDependency,
    current_user: RequireOperator,
) -> TaskSchedule:
    schedule = await session.get(TaskSchedule, schedule_id)
    if schedule is None or schedule.task_type != "steam_review_sync":
        raise HTTPException(status_code=404, detail="Task schedule not found")

    values = request.model_dump(exclude_unset=True)
    if "name" in values and values["name"] is not None:
        schedule.name = values["name"]
    if "is_enabled" in values and values["is_enabled"] is not None:
        schedule.is_enabled = values["is_enabled"]
    if "app_id" in values and values["app_id"] is not None:
        schedule.app_id = values["app_id"]
    if "interval" in values and values["interval"] is not None:
        schedule.interval = values["interval"]
    if "hour" in values and values["hour"] is not None:
        schedule.hour = values["hour"]
    if "options" in values and values["options"] is not None:
        schedule.options = values["options"]
    schedule.minute = 0

    await session.commit()
    await session.refresh(schedule)
    return schedule


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_schedule(
    schedule_id: int,
    session: SessionDependency,
    current_user: RequireOperator,
) -> Response:
    schedule = await session.get(TaskSchedule, schedule_id)
    if schedule is None or schedule.task_type != "steam_review_sync":
        raise HTTPException(status_code=404, detail="Task schedule not found")
    await session.delete(schedule)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
            schedule_name: str | None = None
            if request.schedule_id is not None:
                schedule = await session.get(TaskSchedule, request.schedule_id)
                schedule_name = schedule.name if schedule is not None else None

            await service.sync_reviews(
                ReviewSyncOptions(
                    app_id=request.app_id,
                    schedule_id=request.schedule_id,
                    schedule_name=schedule_name,
                    trigger_type="manual",
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
                task.error_message = format_exception_message(exc)
                await add_task_log(
                    session,
                    sync_job_id,
                    "任务执行失败",
                    level="error",
                    details=format_exception_details(exc),
                )
                await session.commit()
