from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.utils.task_control import SteamTemporarilyUnavailableError, TaskCancelledError

from app.core.database import AsyncSessionLocal, get_session
from app.core.error_utils import format_exception_details, format_exception_message
from app.core.security import RequireOperator
from app.models import SteamGame, SyncJob, TaskLog, TaskSchedule
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
from app.services.review_sync_queue import enqueue_review_sync_job
from app.services.steam_probe_gate import wait_for_steam_availability
from app.services.task_logs import add_task_log
from app.services.task_runtime import (
    finalize_cancelled_task,
    get_steam_sync_lock,
    is_task_cancellable,
    register_cancel_event,
    request_task_cancel,
    unregister_cancel_event,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[SyncJobListItem])
async def list_tasks(
    session: SessionDependency,
    limit: int = Query(default=50, gt=0, le=200),
    schedule_id: int | None = Query(default=None, gt=0),
    app_id: int | None = Query(default=None, gt=0),
) -> list[SyncJobListItem]:
    statement = select(SyncJob, SteamGame.name).outerjoin(
        SteamGame,
        SteamGame.app_id == SyncJob.app_id,
    )
    if schedule_id is not None:
        statement = statement.where(SyncJob.schedule_id == schedule_id)
    if app_id is not None:
        statement = statement.where(SyncJob.app_id == app_id)
    result = await session.execute(
        statement.order_by(desc(SyncJob.created_at), desc(SyncJob.id)).limit(limit)
    )
    items: list[dict] = []
    for job, game_name in result.all():
        payload = SyncJobListItem.model_validate(job).model_dump()
        payload["game_name"] = game_name
        payload["can_cancel"] = is_task_cancellable(job.status)
        items.append(payload)
    return items


@router.post("/reviews-sync", response_model=SyncJobListItem, status_code=202)
async def enqueue_reviews_sync(
    request: ReviewSyncRequest,
    background_tasks: BackgroundTasks,
    session: SessionDependency,
    current_user: RequireOperator,
) -> SyncJob:
    return await enqueue_review_sync_job(session, background_tasks, request, _run_review_sync_job)


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
    existing = await session.execute(
        select(TaskSchedule).where(
            TaskSchedule.task_type == "steam_review_sync",
            TaskSchedule.app_id == request.app_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="A schedule already exists for this game")

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
        existing = await session.execute(
            select(TaskSchedule).where(
                TaskSchedule.task_type == "steam_review_sync",
                TaskSchedule.app_id == values["app_id"],
                TaskSchedule.id != schedule.id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="A schedule already exists for this game")
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
async def get_task_detail(task_id: int, session: SessionDependency) -> SyncJobWithLogsResponse:
    result = await session.execute(
        select(SyncJob, SteamGame.name)
        .outerjoin(SteamGame, SteamGame.app_id == SyncJob.app_id)
        .options(selectinload(SyncJob.logs))
        .where(SyncJob.id == task_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task, game_name = row
    payload = SyncJobWithLogsResponse.model_validate(task).model_dump()
    payload["game_name"] = game_name
    payload["can_cancel"] = is_task_cancellable(task.status)
    return payload


@router.get("/{task_id}/logs", response_model=list[TaskLogResponse])
async def get_task_logs(task_id: int, session: SessionDependency) -> list[TaskLog]:
    result = await session.execute(
        select(TaskLog).where(TaskLog.task_id == task_id).order_by(TaskLog.created_at, TaskLog.id)
    )
    return list(result.scalars().all())


@router.post("/{task_id}/cancel", response_model=SyncJobListItem)
async def cancel_task(
    task_id: int,
    session: SessionDependency,
    current_user: RequireOperator,
) -> SyncJobListItem:
    result = await session.execute(
        select(SyncJob, SteamGame.name)
        .outerjoin(SteamGame, SteamGame.app_id == SyncJob.app_id)
        .where(SyncJob.id == task_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task, game_name = row
    if not is_task_cancellable(task.status):
        raise HTTPException(status_code=409, detail="Task can no longer be cancelled")

    if task.status == "pending":
        await finalize_cancelled_task(
            session,
            task,
            message="任务已取消",
            details={"reason": "cancelled_before_start"},
        )
    elif task.status != "cancel_requested":
        task.status = "cancel_requested"
        await add_task_log(
            session,
            task.id,
            "收到取消请求",
            details={"status": "cancel_requested"},
        )
    request_task_cancel(task.id)
    await session.commit()
    payload = SyncJobListItem.model_validate(task).model_dump()
    payload["game_name"] = game_name
    payload["can_cancel"] = is_task_cancellable(task.status)
    return payload


async def _run_review_sync_job(sync_job_id: int, request: ReviewSyncRequest) -> None:
    cancel_event = register_cancel_event(sync_job_id)
    try:
        async with AsyncSessionLocal() as session:
            task = await session.get(SyncJob, sync_job_id)
            if task is None:
                return
            if task.status == "cancelled":
                return
            if task.status == "cancel_requested":
                await finalize_cancelled_task(
                    session,
                    task,
                    message="任务在启动前已取消",
                    details={"reason": "cancel_requested_before_start"},
                )
                await session.commit()
                return
            try:
                schedule_name: str | None = None
                if request.schedule_id is not None:
                    schedule = await session.get(TaskSchedule, request.schedule_id)
                    schedule_name = schedule.name if schedule is not None else None

                async with get_steam_sync_lock():
                    while True:
                        task = await session.get(SyncJob, sync_job_id)
                        if task is None:
                            return
                        if task.status == "cancelled":
                            return
                        if task.status == "cancel_requested":
                            await finalize_cancelled_task(
                                session,
                                task,
                                message="任务已取消",
                                details={"reason": "cancel_requested_while_waiting"},
                            )
                            await session.commit()
                            return
                        try:
                            await wait_for_steam_availability(
                                session,
                                task,
                                cancel_event=cancel_event,
                            )
                        except TaskCancelledError:
                            await session.refresh(task)
                            await finalize_cancelled_task(
                                session,
                                task,
                                message="任务已取消",
                                details={"reason": "cancelled_during_probe_wait"},
                            )
                            await session.commit()
                            return

                        service = SteamReviewSyncService(session, cancel_event=cancel_event)
                        try:
                            result = await service.sync_reviews(
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
                        except SteamTemporarilyUnavailableError:
                            continue
                        if result.status in {"success", "partial_success", "cancelled"}:
                            return
            except Exception as exc:
                task = await session.get(SyncJob, sync_job_id)
                if task is not None and task.status not in {"cancelled", "failed"}:
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
    finally:
        unregister_cancel_event(sync_job_id)
