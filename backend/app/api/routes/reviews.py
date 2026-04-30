from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import Select, asc, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_session
from app.core.security import RequireOperator
from app.models import ReplyDraft, SteamReview, SyncJob
from app.schemas import (
    BulkGenerateReplyRequest,
    BulkGenerateReplyResponse,
    BulkReviewStatusUpdateRequest,
    BulkSendReplyRequest,
    BulkSendReplyResponse,
    GenerateReplyResponse,
    ReplyDraftResponse,
    ReviewDetailResponse,
    ReviewListResponse,
    ReviewStatusUpdateRequest,
    ReviewStatusUpdateResponse,
    ReviewSyncRequest,
    ReviewSyncResponse,
    SendReplyRequest,
    SendReplyResponse,
    SyncJobDetailResponse,
    SyncJobListItem,
)
from app.services.developer_replies import DeveloperReplyError, DeveloperReplyService
from app.services.reply_generation import ReplyGenerationError, ReplyGenerationService
from app.services.review_sync import ReviewSyncOptions, SteamReviewSyncService
from app.services.task_logs import add_task_log

router = APIRouter(prefix="/reviews", tags=["reviews"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CHINA_TZ = ZoneInfo("Asia/Shanghai")


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
    session: SessionDependency,
    current_user: RequireOperator,
) -> BulkGenerateReplyResponse:
    task = await _create_background_job(
        session,
        job_type="bulk_reply_generation",
        source_type="aliyun_api",
        requested_limit=len(request.review_ids),
        details={"review_ids": request.review_ids, "created_by_user_id": current_user.id},
    )
    background_tasks.add_task(_generate_reply_drafts_in_background, task.id, request.review_ids)
    return BulkGenerateReplyResponse(
        accepted_count=len(request.review_ids),
        review_ids=request.review_ids,
        task_id=task.id,
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


@router.post("/{review_id}/regenerate-reply", response_model=GenerateReplyResponse)
async def regenerate_reply(
    review_id: int,
    session: SessionDependency,
) -> GenerateReplyResponse:
    return await generate_reply(review_id, session)


@router.post("/{review_id}/send-reply", response_model=SendReplyResponse)
async def send_reply(
    review_id: int,
    request: SendReplyRequest,
    session: SessionDependency,
    current_user: RequireOperator,
) -> SendReplyResponse:
    service = DeveloperReplyService(session)
    try:
        record = await service.send_reply(
            review_id,
            confirmed=request.confirmed,
            draft_id=request.draft_id,
            content=request.content,
            sent_by_user_id=current_user.id,
        )
    except DeveloperReplyError as exc:
        status_code = 404 if str(exc) in {"Review not found", "Reply draft not found"} else 400
        if exc.record_id is not None:
            status_code = 502
        raise HTTPException(
            status_code=status_code,
            detail={"message": str(exc), "record_id": exc.record_id},
        ) from exc
    return SendReplyResponse(record=record)


@router.post("/bulk-send-reply", response_model=BulkSendReplyResponse, status_code=202)
async def bulk_send_reply(
    request: BulkSendReplyRequest,
    background_tasks: BackgroundTasks,
    session: SessionDependency,
    current_user: RequireOperator,
) -> BulkSendReplyResponse:
    if not request.confirmed:
        raise HTTPException(status_code=400, detail="Bulk send requires confirmation")
    task = await _create_background_job(
        session,
        job_type="bulk_developer_reply_send",
        source_type="steam_community",
        requested_limit=len(request.review_ids),
        details={"review_ids": request.review_ids, "created_by_user_id": current_user.id},
    )
    background_tasks.add_task(
        _send_replies_in_background,
        task.id,
        request.review_ids,
        current_user.id,
    )
    return BulkSendReplyResponse(
        accepted_count=len(request.review_ids),
        review_ids=request.review_ids,
        task_id=task.id,
    )


@router.get("/{review_id}/reply-drafts", response_model=list[ReplyDraftResponse])
async def list_review_reply_drafts(
    review_id: int,
    session: SessionDependency,
) -> list[ReplyDraft]:
    review = await session.get(SteamReview, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    result = await session.execute(
        select(ReplyDraft)
        .where(ReplyDraft.review_id == review_id)
        .order_by(desc(ReplyDraft.created_at), desc(ReplyDraft.id))
    )
    return list(result.scalars().all())


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


async def _generate_reply_drafts_in_background(task_id: int, review_ids: list[int]) -> None:
    async with AsyncSessionLocal() as session:
        task = await session.get(SyncJob, task_id)
        if task is None:
            return
        task.status = "running"
        task.started_at = datetime.now(tz=CHINA_TZ)
        await add_task_log(
            session,
            task.id,
            "批量生成回复草稿开始",
            details={"review_count": len(review_ids)},
        )
        success_count = 0
        failed_count = 0
        service = ReplyGenerationService(session)
        for review_id in review_ids:
            try:
                await service.generate_for_review(review_id)
                success_count += 1
                await add_task_log(
                    session,
                    task.id,
                    "回复草稿生成成功",
                    details={"review_id": review_id},
                )
            except ReplyGenerationError:
                failed_count += 1
                await add_task_log(
                    session,
                    task.id,
                    "回复草稿生成失败",
                    level="error",
                    details={"review_id": review_id},
                )
                continue
        task.status = task_status_from_counts(success_count, failed_count)
        task.inserted_count = success_count
        task.skipped_count = failed_count
        task.finished_at = datetime.now(tz=CHINA_TZ)
        await add_task_log(
            session,
            task.id,
            "批量生成回复草稿完成",
            details={"success_count": success_count, "failed_count": failed_count},
        )
        await session.commit()


async def _send_replies_in_background(
    task_id: int,
    review_ids: list[int],
    sent_by_user_id: int | None,
) -> None:
    async with AsyncSessionLocal() as session:
        task = await session.get(SyncJob, task_id)
        if task is None:
            return
        task.status = "running"
        task.started_at = datetime.now(tz=CHINA_TZ)
        await add_task_log(
            session,
            task.id,
            "批量发送开发者回复开始",
            details={"review_count": len(review_ids), "sent_by_user_id": sent_by_user_id},
        )
        success_count = 0
        failed_count = 0
        service = DeveloperReplyService(session)
        for review_id in review_ids:
            try:
                await service.send_reply(
                    review_id,
                    confirmed=True,
                    sent_by_user_id=sent_by_user_id,
                )
                success_count += 1
                await add_task_log(
                    session,
                    task.id,
                    "开发者回复发送成功",
                    details={"review_id": review_id},
                )
            except DeveloperReplyError:
                failed_count += 1
                await add_task_log(
                    session,
                    task.id,
                    "开发者回复发送失败",
                    level="error",
                    details={"review_id": review_id},
                )
                continue
        task.status = task_status_from_counts(success_count, failed_count)
        task.inserted_count = success_count
        task.skipped_count = failed_count
        task.finished_at = datetime.now(tz=CHINA_TZ)
        await add_task_log(
            session,
            task.id,
            "批量发送开发者回复完成",
            details={"success_count": success_count, "failed_count": failed_count},
        )
        await session.commit()


async def _create_background_job(
    session: AsyncSession,
    *,
    job_type: str,
    source_type: str,
    requested_limit: int,
    details: dict,
) -> SyncJob:
    task = SyncJob(
        job_type=job_type,
        source_type=source_type,
        status="pending",
        requested_limit=requested_limit,
    )
    session.add(task)
    await session.flush()
    await add_task_log(session, task.id, "任务已进入队列", details=details)
    await session.commit()
    await session.refresh(task)
    return task


def task_status_from_counts(success_count: int, failed_count: int) -> str:
    if failed_count == 0:
        return "success"
    if success_count == 0:
        return "failed"
    return "partial_success"


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
