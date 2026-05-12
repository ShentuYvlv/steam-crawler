from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import DeveloperReply, SteamGame, SteamReview
from app.schemas import StatsOverviewResponse, StatsTimeseriesItem, StatsTimeseriesResponse

router = APIRouter(prefix="/stats", tags=["stats"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/overview", response_model=StatsOverviewResponse)
async def get_stats_overview(
    session: SessionDependency,
    scope: str = Query(default="owned", pattern="^(owned|competitor|all)$"),
    app_id: int | None = Query(default=None, gt=0),
) -> StatsOverviewResponse:
    await _validate_stats_scope(session, scope=scope, app_id=app_id)
    total_reviews = await session.scalar(_scoped_review_count_query(scope=scope, app_id=app_id)) or 0
    positive_reviews = (
        await session.scalar(
            _scoped_review_count_query(scope=scope, app_id=app_id).where(
                SteamReview.voted_up.is_(True)
            )
        )
        or 0
    )
    negative_reviews = (
        await session.scalar(
            _scoped_review_count_query(scope=scope, app_id=app_id).where(
                SteamReview.voted_up.is_(False)
            )
        )
        or 0
    )
    replied_reviews = (
        await session.scalar(
            _scoped_review_count_query(scope=scope, app_id=app_id).where(
                SteamReview.reply_status == "replied"
            )
        )
        or 0
    )
    pending_reviews = (
        await session.scalar(
            _scoped_review_count_query(scope=scope, app_id=app_id).where(
                SteamReview.processing_status == "pending",
                SteamReview.reply_status != "replied",
            )
        )
        or 0
    )
    ignored_reviews = (
        await session.scalar(
            _scoped_review_count_query(scope=scope, app_id=app_id).where(
                SteamReview.processing_status == "ignored"
            )
        )
        or 0
    )
    sent_reply_records = (
        await session.scalar(
            _scoped_reply_count_query(scope=scope, app_id=app_id).where(
                DeveloperReply.status == "sent"
            )
        )
        or 0
    )
    failed_reply_records = (
        await session.scalar(
            _scoped_reply_count_query(scope=scope, app_id=app_id).where(
                DeveloperReply.status == "failed"
            )
        )
        or 0
    )
    reply_record_total = sent_reply_records + failed_reply_records

    return StatsOverviewResponse(
        total_reviews=total_reviews,
        positive_reviews=positive_reviews,
        negative_reviews=negative_reviews,
        replied_reviews=replied_reviews,
        pending_reviews=pending_reviews,
        ignored_reviews=ignored_reviews,
        positive_rate=round(positive_reviews / total_reviews, 4) if total_reviews else 0,
        reply_success_rate=round(sent_reply_records / reply_record_total, 4)
        if reply_record_total
        else 0,
    )


@router.get("/timeseries", response_model=StatsTimeseriesResponse)
async def get_stats_timeseries(
    session: SessionDependency,
    scope: str = Query(default="owned", pattern="^(owned|competitor|all)$"),
    app_id: int | None = Query(default=None, gt=0),
    days: int = Query(default=14, ge=1, le=90),
) -> StatsTimeseriesResponse:
    await _validate_stats_scope(session, scope=scope, app_id=app_id)
    start_date = date.today() - timedelta(days=days - 1)
    review_date = cast(SteamReview.timestamp_created, Date)
    reply_date = cast(DeveloperReply.sent_at, Date)

    review_statement = (
        select(review_date, func.count(SteamReview.id))
        .select_from(SteamReview)
        .join(SteamGame, SteamGame.app_id == SteamReview.app_id)
        .where(SteamReview.timestamp_created.is_not(None), review_date >= start_date)
    )
    reply_statement = (
        select(reply_date, func.count(DeveloperReply.id))
        .select_from(DeveloperReply)
        .join(SteamReview, SteamReview.id == DeveloperReply.review_id)
        .join(SteamGame, SteamGame.app_id == SteamReview.app_id)
        .where(DeveloperReply.sent_at.is_not(None), reply_date >= start_date)
    )
    review_statement = _apply_review_scope_filters(review_statement, scope=scope, app_id=app_id)
    reply_statement = _apply_reply_scope_filters(reply_statement, scope=scope, app_id=app_id)

    review_result = await session.execute(review_statement.group_by(review_date))
    reply_result = await session.execute(reply_statement.group_by(reply_date))
    reviews_by_date = {row[0]: row[1] for row in review_result.all()}
    replies_by_date = {row[0]: row[1] for row in reply_result.all()}

    items = []
    for offset in range(days):
        current_date = start_date + timedelta(days=offset)
        items.append(
            StatsTimeseriesItem(
                date=current_date,
                new_reviews=reviews_by_date.get(current_date, 0),
                sent_replies=replies_by_date.get(current_date, 0),
            )
        )
    return StatsTimeseriesResponse(items=items)


def _apply_review_scope_filters(statement, *, scope: str, app_id: int | None):
    if scope == "owned":
        statement = statement.where(SteamGame.game_scope == "owned")
    elif scope == "competitor":
        statement = statement.where(SteamGame.game_scope == "competitor")
    if app_id is not None:
        statement = statement.where(SteamReview.app_id == app_id)
    return statement


def _apply_reply_scope_filters(statement, *, scope: str, app_id: int | None):
    if scope == "owned":
        statement = statement.where(SteamGame.game_scope == "owned")
    elif scope == "competitor":
        statement = statement.where(SteamGame.game_scope == "competitor")
    if app_id is not None:
        statement = statement.where(SteamReview.app_id == app_id)
    return statement


def _scoped_review_count_query(*, scope: str, app_id: int | None):
    statement = (
        select(func.count(SteamReview.id))
        .select_from(SteamReview)
        .join(SteamGame, SteamGame.app_id == SteamReview.app_id)
    )
    return _apply_review_scope_filters(statement, scope=scope, app_id=app_id)


def _scoped_reply_count_query(*, scope: str, app_id: int | None):
    statement = (
        select(func.count(DeveloperReply.id))
        .select_from(DeveloperReply)
        .join(SteamReview, SteamReview.id == DeveloperReply.review_id)
        .join(SteamGame, SteamGame.app_id == SteamReview.app_id)
    )
    return _apply_reply_scope_filters(statement, scope=scope, app_id=app_id)


async def _validate_stats_scope(
    session: AsyncSession,
    *,
    scope: str,
    app_id: int | None,
) -> None:
    if app_id is None:
        return
    game = await session.get(SteamGame, app_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if scope != "all" and game.game_scope != scope:
        raise HTTPException(
            status_code=400,
            detail="Selected game does not belong to requested scope",
        )
