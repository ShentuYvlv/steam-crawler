from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import DeveloperReply, SteamReview
from app.schemas import StatsOverviewResponse, StatsTimeseriesItem, StatsTimeseriesResponse

router = APIRouter(prefix="/stats", tags=["stats"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/overview", response_model=StatsOverviewResponse)
async def get_stats_overview(session: SessionDependency) -> StatsOverviewResponse:
    total_reviews = await session.scalar(select(func.count(SteamReview.id))) or 0
    positive_reviews = (
        await session.scalar(
            select(func.count(SteamReview.id)).where(SteamReview.voted_up.is_(True))
        )
        or 0
    )
    negative_reviews = (
        await session.scalar(
            select(func.count(SteamReview.id)).where(SteamReview.voted_up.is_(False))
        )
        or 0
    )
    replied_reviews = (
        await session.scalar(
            select(func.count(SteamReview.id)).where(SteamReview.reply_status == "replied")
        )
        or 0
    )
    pending_reviews = (
        await session.scalar(
            select(func.count(SteamReview.id)).where(SteamReview.processing_status == "pending")
        )
        or 0
    )
    ignored_reviews = (
        await session.scalar(
            select(func.count(SteamReview.id)).where(SteamReview.processing_status == "ignored")
        )
        or 0
    )
    sent_reply_records = (
        await session.scalar(
            select(func.count(DeveloperReply.id)).where(DeveloperReply.status == "sent")
        )
        or 0
    )
    failed_reply_records = (
        await session.scalar(
            select(func.count(DeveloperReply.id)).where(DeveloperReply.status == "failed")
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
    days: int = Query(default=14, ge=1, le=90),
) -> StatsTimeseriesResponse:
    start_date = date.today() - timedelta(days=days - 1)
    review_date = cast(SteamReview.timestamp_created, Date)
    reply_date = cast(DeveloperReply.sent_at, Date)

    review_result = await session.execute(
        select(review_date, func.count(SteamReview.id))
        .where(SteamReview.timestamp_created.is_not(None), review_date >= start_date)
        .group_by(review_date)
    )
    reply_result = await session.execute(
        select(reply_date, func.count(DeveloperReply.id))
        .where(DeveloperReply.sent_at.is_not(None), reply_date >= start_date)
        .group_by(reply_date)
    )
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
