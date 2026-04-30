from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import Select, asc, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_session
from app.models import SteamReview, SyncJob
from app.schemas import (
    BulkGenerateReplyRequest,
    BulkGenerateReplyResponse,
    BulkReviewStatusUpdateRequest,
    GenerateReplyResponse,
    ReviewDetailResponse,
    ReviewListResponse,
    ReviewStatusUpdateRequest,
    ReviewStatusUpdateResponse,
    ReviewSyncRequest,
    ReviewSyncResponse,
    SyncJobDetailResponse,
    SyncJobListItem,
)
from app.services.reply_generation import ReplyGenerationError, ReplyGenerationService
from app.services.review_sync import ReviewSyncOptions, SteamReviewSyncService

router = APIRouter(prefix="/reviews", tags=["reviews"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=ReviewListResponse)
async def list_reviews(
    session: SessionDependency,
    app_id: int | None = Query(default=None, gt=0),
    voted_up: bool | None = None,
    min_votes_up: int | None = Query(default=None, ge=0),
    max_votes_up: int | None = Query(default=None, ge=0),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    min_playtime: float | None = Query(default=None, ge=0),
    max_playtime: float | None = Query(default=None, ge=0),
    processing_status: str | None = None,
    reply_status: str | None = None,
    keyword: str | None = None,
    sort_by: str = Query(default="timestamp_created"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> ReviewListResponse:
    statement = _apply_review_filters(
        select(SteamReview),
        app_id=app_id,
        voted_up=voted_up,
        min_votes_up=min_votes_up,
        max_votes_up=max_votes_up,
        created_from=created_from,
        created_to=created_to,
        min_playtime=min_playtime,
        max_playtime=max_playtime,
        processing_status=processing_status,
        reply_status=reply_status,
        keyword=keyword,
    )
    count_statement = _apply_review_filters(
        select(func.count(SteamReview.id)),
        app_id=app_id,
        voted_up=voted_up,
        min_votes_up=min_votes_up,
        max_votes_up=max_votes_up,
        created_from=created_from,
        created_to=created_to,
        min_playtime=min_playtime,
        max_playtime=max_playtime,
        processing_status=processing_status,
        reply_status=reply_status,
        keyword=keyword,
    )
    total = await session.scalar(count_statement)
    sort_column = _get_review_sort_column(sort_by)
    sort_expression = asc(sort_column) if sort_order == "asc" else desc(sort_column)
    result = await session.execute(
        statement.order_by(sort_expression, desc(SteamReview.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return ReviewListResponse(
        items=list(result.scalars().all()),
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.post("/sync", response_model=ReviewSyncResponse)
async def sync_reviews(
    request: ReviewSyncRequest,
    session: SessionDependency,
) -> ReviewSyncResponse:
    service = SteamReviewSyncService(session)
    result = await service.sync_reviews(
        ReviewSyncOptions(
            app_id=request.app_id,
            limit=request.limit,
            language=request.language,
            filter=request.filter,
            review_type=request.review_type,
            purchase_type=request.purchase_type,
            use_review_quality=request.use_review_quality,
            per_page=request.per_page,
        )
    )
    return ReviewSyncResponse(
        sync_job_id=result.sync_job_id,
        app_id=result.app_id,
        inserted=result.inserted,
        updated=result.updated,
        skipped=result.skipped,
        status=result.status,
        query_summary=result.query_summary,
    )


@router.get("/sync-jobs", response_model=list[SyncJobListItem])
async def list_sync_jobs(
    session: SessionDependency,
    limit: int = Query(default=50, gt=0, le=200),
) -> list[SyncJob]:
    result = await session.execute(
        select(SyncJob).order_by(desc(SyncJob.created_at), desc(SyncJob.id)).limit(limit)
    )
    return list(result.scalars().all())


@router.get("/sync-jobs/{sync_job_id}", response_model=SyncJobDetailResponse)
async def get_sync_job(
    sync_job_id: int,
    session: SessionDependency,
) -> SyncJob:
    sync_job = await session.get(SyncJob, sync_job_id)
    if sync_job is None:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return sync_job


@router.post("/bulk-status", response_model=ReviewStatusUpdateResponse)
async def bulk_update_review_status(
    request: BulkReviewStatusUpdateRequest,
    session: SessionDependency,
) -> ReviewStatusUpdateResponse:
    values = _status_update_values(request)
    if not values:
        raise HTTPException(status_code=400, detail="No status fields provided")

    result = await session.execute(
        update(SteamReview).where(SteamReview.id.in_(request.review_ids)).values(**values)
    )
    await session.commit()
    return ReviewStatusUpdateResponse(updated_count=result.rowcount or 0)


@router.post("/bulk-generate-reply", response_model=BulkGenerateReplyResponse, status_code=202)
async def bulk_generate_reply(
    request: BulkGenerateReplyRequest,
    background_tasks: BackgroundTasks,
) -> BulkGenerateReplyResponse:
    background_tasks.add_task(_generate_reply_drafts_in_background, request.review_ids)
    return BulkGenerateReplyResponse(
        accepted_count=len(request.review_ids),
        review_ids=request.review_ids,
    )


@router.post("/{review_id}/generate-reply", response_model=GenerateReplyResponse)
async def generate_reply(
    review_id: int,
    session: SessionDependency,
) -> GenerateReplyResponse:
    service = ReplyGenerationService(session)
    try:
        result = await service.generate_for_review(review_id)
    except ReplyGenerationError as exc:
        status_code = 404 if str(exc) == "Review not found" else 400
        if exc.draft_id is not None:
            status_code = 502
        raise HTTPException(
            status_code=status_code,
            detail={"message": str(exc), "draft_id": exc.draft_id},
        ) from exc
    return GenerateReplyResponse(draft=result.draft)


@router.get("/{review_id}", response_model=ReviewDetailResponse)
async def get_review(
    review_id: int,
    session: SessionDependency,
) -> SteamReview:
    review = await session.get(SteamReview, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.patch("/{review_id}/status", response_model=ReviewStatusUpdateResponse)
async def update_review_status(
    review_id: int,
    request: ReviewStatusUpdateRequest,
    session: SessionDependency,
) -> ReviewStatusUpdateResponse:
    values = _status_update_values(request)
    if not values:
        raise HTTPException(status_code=400, detail="No status fields provided")

    review = await session.get(SteamReview, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")

    for key, value in values.items():
        setattr(review, key, value)
    await session.commit()
    return ReviewStatusUpdateResponse(updated_count=1)


async def _generate_reply_drafts_in_background(review_ids: list[int]) -> None:
    async with AsyncSessionLocal() as session:
        service = ReplyGenerationService(session)
        for review_id in review_ids:
            try:
                await service.generate_for_review(review_id)
            except ReplyGenerationError:
                continue


def _apply_review_filters(
    statement: Select,
    *,
    app_id: int | None,
    voted_up: bool | None,
    min_votes_up: int | None,
    max_votes_up: int | None,
    created_from: datetime | None,
    created_to: datetime | None,
    min_playtime: float | None,
    max_playtime: float | None,
    processing_status: str | None,
    reply_status: str | None,
    keyword: str | None,
) -> Select:
    if app_id is not None:
        statement = statement.where(SteamReview.app_id == app_id)
    if voted_up is not None:
        statement = statement.where(SteamReview.voted_up == voted_up)
    if min_votes_up is not None:
        statement = statement.where(SteamReview.votes_up >= min_votes_up)
    if max_votes_up is not None:
        statement = statement.where(SteamReview.votes_up <= max_votes_up)
    if created_from:
        statement = statement.where(SteamReview.timestamp_created >= created_from)
    if created_to:
        statement = statement.where(SteamReview.timestamp_created <= created_to)
    if min_playtime is not None:
        statement = statement.where(SteamReview.playtime_forever >= min_playtime)
    if max_playtime is not None:
        statement = statement.where(SteamReview.playtime_forever <= max_playtime)
    if processing_status:
        statement = statement.where(SteamReview.processing_status == processing_status)
    if reply_status:
        statement = statement.where(SteamReview.reply_status == reply_status)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        statement = statement.where(
            or_(
                SteamReview.review_text.ilike(pattern),
                SteamReview.persona_name.ilike(pattern),
                SteamReview.recommendation_id.ilike(pattern),
                SteamReview.steam_id.ilike(pattern),
            )
        )
    return statement


def _get_review_sort_column(sort_by: str):
    sort_columns = {
        "votes_up": SteamReview.votes_up,
        "timestamp_created": SteamReview.timestamp_created,
        "playtime_forever": SteamReview.playtime_forever,
        "playtime_at_review": SteamReview.playtime_at_review,
    }
    return sort_columns.get(sort_by, SteamReview.timestamp_created)


def _status_update_values(
    request: ReviewStatusUpdateRequest | BulkReviewStatusUpdateRequest,
) -> dict[str, str]:
    values = {}
    if request.processing_status is not None:
        values["processing_status"] = request.processing_status
    if request.reply_status is not None:
        values["reply_status"] = request.reply_status
    return values
