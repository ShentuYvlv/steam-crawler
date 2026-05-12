from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.tasks import _run_review_sync_job
from app.core.database import get_session
from app.core.security import RequireOperator
from app.models import SteamGame, SteamReview, SyncJob, TaskSchedule
from app.schemas import (
    GameCreateRequest,
    GameListItem,
    GameSyncBatchResponse,
    GameUpdateRequest,
    ReviewSyncRequest,
)
from app.services.review_sync_queue import enqueue_review_sync_job

router = APIRouter(prefix="/games", tags=["games"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[GameListItem])
async def list_games(session: SessionDependency) -> list[GameListItem]:
    games_result = await session.execute(
        select(
            SteamGame.app_id,
            SteamGame.name,
            SteamGame.game_scope,
            func.count(SteamReview.id).label("review_count"),
        )
        .outerjoin(SteamReview, SteamReview.app_id == SteamGame.app_id)
        .group_by(SteamGame.app_id, SteamGame.name, SteamGame.game_scope)
        .order_by(func.lower(func.coalesce(SteamGame.name, "")), SteamGame.app_id)
    )
    schedule_result = await session.execute(
        select(TaskSchedule).where(TaskSchedule.task_type == "steam_review_sync")
    )
    latest_jobs_result = await session.execute(
        select(SyncJob)
        .where(SyncJob.app_id.is_not(None))
        .order_by(SyncJob.created_at.desc(), SyncJob.id.desc())
    )

    schedules_by_app_id = {
        schedule.app_id: schedule
        for schedule in schedule_result.scalars().all()
        if schedule.app_id is not None
    }
    latest_job_by_app_id: dict[int, SyncJob] = {}
    for job in latest_jobs_result.scalars().all():
        if job.app_id is None or job.app_id in latest_job_by_app_id:
            continue
        latest_job_by_app_id[job.app_id] = job

    items: list[GameListItem] = []
    for app_id, name, game_scope, review_count in games_result.all():
        schedule = schedules_by_app_id.get(app_id)
        latest_job = latest_job_by_app_id.get(app_id)
        items.append(
                GameListItem(
                    app_id=app_id,
                    name=name,
                    game_scope=game_scope,
                review_count=review_count,
                has_schedule=schedule is not None,
                schedule_id=schedule.id if schedule else None,
                schedule_name=schedule.name if schedule else None,
                schedule_enabled=schedule.is_enabled if schedule else False,
                schedule_hour=schedule.hour if schedule else None,
                schedule_options=schedule.options if schedule else None,
                latest_task_id=latest_job.id if latest_job else None,
                latest_task_status=latest_job.status if latest_job else None,
                latest_task_finished_at=latest_job.finished_at if latest_job else None,
            )
        )
    return items


@router.post("", response_model=GameListItem, status_code=status.HTTP_201_CREATED)
async def create_game(
    request: GameCreateRequest,
    session: SessionDependency,
    current_user: RequireOperator,
) -> GameListItem:
    existing = await session.get(SteamGame, request.app_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Game already exists")

    game = SteamGame(app_id=request.app_id, name=request.name, game_scope=request.game_scope)
    session.add(game)
    schedule = None
    if request.sync is not None:
        schedule = TaskSchedule(
            name=request.name,
            task_type="steam_review_sync",
            is_enabled=request.sync.enabled,
            app_id=request.app_id,
            interval="daily",
            hour=request.sync.hour,
            minute=0,
            options=request.sync.to_schedule_options(),
        )
        session.add(schedule)
    await session.commit()
    await session.refresh(game)
    if schedule is not None:
        await session.refresh(schedule)
    return GameListItem(
        app_id=game.app_id,
        name=game.name,
        game_scope=game.game_scope,
        review_count=0,
        has_schedule=schedule is not None,
        schedule_id=schedule.id if schedule else None,
        schedule_name=schedule.name if schedule else None,
        schedule_enabled=schedule.is_enabled if schedule else False,
        schedule_hour=schedule.hour if schedule else None,
        schedule_options=schedule.options if schedule else None,
        latest_task_id=None,
        latest_task_status=None,
        latest_task_finished_at=None,
    )


@router.patch("/{app_id}", response_model=GameListItem)
async def update_game(
    app_id: int,
    request: GameUpdateRequest,
    session: SessionDependency,
    current_user: RequireOperator,
) -> GameListItem:
    game = await session.get(SteamGame, app_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    game.name = request.name
    game.game_scope = request.game_scope
    schedule_result = await session.execute(
        select(TaskSchedule).where(
            TaskSchedule.task_type == "steam_review_sync",
            TaskSchedule.app_id == app_id,
        )
    )
    schedule = schedule_result.scalar_one_or_none()

    if request.sync is None:
        if schedule is not None:
            schedule.name = request.name
    elif schedule is None:
        schedule = TaskSchedule(
            name=request.name,
            task_type="steam_review_sync",
            is_enabled=request.sync.enabled,
            app_id=app_id,
            interval="daily",
            hour=request.sync.hour,
            minute=0,
            options=request.sync.to_schedule_options(),
        )
        session.add(schedule)
    else:
        schedule.name = request.name
        schedule.is_enabled = request.sync.enabled
        schedule.interval = "daily"
        schedule.hour = request.sync.hour
        schedule.minute = 0
        schedule.options = request.sync.to_schedule_options()

    await session.commit()
    await session.refresh(game)
    if schedule is not None:
        await session.refresh(schedule)
    review_count = await _count_reviews(session, app_id)
    latest_job = await _get_latest_job(session, app_id)
    return GameListItem(
        app_id=game.app_id,
        name=game.name,
        game_scope=game.game_scope,
        review_count=review_count,
        has_schedule=schedule is not None,
        schedule_id=schedule.id if schedule else None,
        schedule_name=schedule.name if schedule else None,
        schedule_enabled=schedule.is_enabled if schedule else False,
        schedule_hour=schedule.hour if schedule else None,
        schedule_options=schedule.options if schedule else None,
        latest_task_id=latest_job.id if latest_job else None,
        latest_task_status=latest_job.status if latest_job else None,
        latest_task_finished_at=latest_job.finished_at if latest_job else None,
    )


@router.post(
    "/{app_id}/sync",
    response_model=GameSyncBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sync_single_game(
    app_id: int,
    background_tasks: BackgroundTasks,
    session: SessionDependency,
    current_user: RequireOperator,
) -> GameSyncBatchResponse:
    game = await session.get(SteamGame, app_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    task = await _enqueue_game_sync(session, background_tasks, app_id)
    return GameSyncBatchResponse(accepted_count=1, task_ids=[task.id])


@router.post(
    "/sync-all",
    response_model=GameSyncBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sync_all_games(
    background_tasks: BackgroundTasks,
    session: SessionDependency,
    current_user: RequireOperator,
) -> GameSyncBatchResponse:
    result = await session.execute(
        select(SteamGame.app_id).order_by(
            func.lower(func.coalesce(SteamGame.name, "")),
            SteamGame.app_id,
        )
    )
    app_ids = [row[0] for row in result.all()]
    task_ids: list[int] = []
    for app_id in app_ids:
        task = await _enqueue_game_sync(session, background_tasks, app_id)
        task_ids.append(task.id)
    return GameSyncBatchResponse(accepted_count=len(task_ids), task_ids=task_ids)


async def _enqueue_game_sync(
    session: AsyncSession,
    background_tasks: BackgroundTasks,
    app_id: int,
) -> SyncJob:
    schedule_result = await session.execute(
        select(TaskSchedule).where(
            TaskSchedule.task_type == "steam_review_sync",
            TaskSchedule.app_id == app_id,
        )
    )
    schedule = schedule_result.scalar_one_or_none()
    options = schedule.options or {} if schedule is not None else {}
    request = ReviewSyncRequest(
        app_id=app_id,
        schedule_id=schedule.id if schedule else None,
        language=str(options.get("language") or "schinese"),
        filter=str(options.get("filter") or "recent"),
        review_type=str(options.get("review_type") or "all"),
        purchase_type=str(options.get("purchase_type") or "all"),
        use_review_quality=bool(options.get("use_review_quality", True)),
        per_page=int(options.get("per_page") or 100),
    )
    return await enqueue_review_sync_job(session, background_tasks, request, _run_review_sync_job)


async def _count_reviews(session: AsyncSession, app_id: int) -> int:
    result = await session.execute(
        select(func.count(SteamReview.id)).where(SteamReview.app_id == app_id)
    )
    return int(result.scalar() or 0)


async def _get_latest_job(session: AsyncSession, app_id: int) -> SyncJob | None:
    result = await session.execute(
        select(SyncJob)
        .where(SyncJob.app_id == app_id)
        .order_by(SyncJob.created_at.desc(), SyncJob.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
