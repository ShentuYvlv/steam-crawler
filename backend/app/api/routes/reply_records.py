from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import RequireOperator
from app.models import DeveloperReply, OperationLog, ReplyDraft, SteamGame, SteamReview
from app.schemas import (
    DeleteRequestCreate,
    ReplyDraftAuditListItem,
    ReplyRecordListItem,
    ReplyRecordResponse,
)

router = APIRouter(prefix="/reply-records", tags=["reply-records"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CHINA_TZ = ZoneInfo("Asia/Shanghai")
ACTIVE_AUDIT_DRAFT_STATUSES = ["pending_review", "generation_failed", "send_failed", "sending"]
ACTIVE_AUDIT_REVIEW_STATUSES = ["drafted", "generation_failed", "send_failed", "sending"]


@router.get("", response_model=list[ReplyRecordListItem])
async def list_reply_records(
    session: SessionDependency,
    status: str | None = None,
    app_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=200, gt=0, le=500),
) -> list[ReplyRecordListItem]:
    statement = (
        select(DeveloperReply, SteamReview, SteamGame)
        .join(SteamReview, SteamReview.id == DeveloperReply.review_id)
        .join(SteamGame, SteamGame.app_id == SteamReview.app_id)
        .where(SteamGame.game_scope == "owned")
        .order_by(
            desc(SteamReview.timestamp_created),
            desc(DeveloperReply.sent_at),
            desc(DeveloperReply.id),
        )
        .limit(limit)
    )
    if status:
        statement = statement.where(DeveloperReply.status == status)
    if app_id:
        statement = statement.where(SteamReview.app_id == app_id)

    result = await session.execute(statement)
    items: list[ReplyRecordListItem] = []
    for record, review, game in result.all():
        items.append(
            ReplyRecordListItem(
                **ReplyRecordResponse.model_validate(record).model_dump(),
                app_id=review.app_id,
                game_name=game.name,
                review_url=review.review_url,
                review_text=review.review_text,
                persona_name=review.persona_name,
                voted_up=review.voted_up,
                timestamp_created=review.timestamp_created,
            )
        )
    return items


@router.get("/audit-queue", response_model=list[ReplyDraftAuditListItem])
async def list_reply_audit_queue(
    session: SessionDependency,
    app_id: int | None = Query(default=None, gt=0),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, gt=0, le=500),
) -> list[ReplyDraftAuditListItem]:
    latest_active_draft_subquery = (
        select(
            ReplyDraft.review_id.label("review_id"),
            func.max(ReplyDraft.id).label("draft_id"),
        )
        .where(ReplyDraft.status.in_(ACTIVE_AUDIT_DRAFT_STATUSES))
        .group_by(ReplyDraft.review_id)
        .subquery()
    )
    latest_reply_subquery = (
        select(
            DeveloperReply.review_id.label("review_id"),
            func.max(DeveloperReply.id).label("reply_record_id"),
        )
        .group_by(DeveloperReply.review_id)
        .subquery()
    )
    statement = (
        select(ReplyDraft, SteamReview, SteamGame, DeveloperReply)
        .join(latest_active_draft_subquery, latest_active_draft_subquery.c.draft_id == ReplyDraft.id)
        .join(SteamReview, SteamReview.id == ReplyDraft.review_id)
        .join(SteamGame, SteamGame.app_id == SteamReview.app_id)
        .outerjoin(
            latest_reply_subquery,
            latest_reply_subquery.c.review_id == SteamReview.id,
        )
        .outerjoin(
            DeveloperReply,
            DeveloperReply.id == latest_reply_subquery.c.reply_record_id,
        )
        .where(SteamGame.game_scope == "owned")
        .where(ReplyDraft.status.in_(ACTIVE_AUDIT_DRAFT_STATUSES))
        .where(SteamReview.reply_status.in_(ACTIVE_AUDIT_REVIEW_STATUSES))
        .order_by(
            SteamGame.name.asc(),
            desc(SteamReview.timestamp_created),
            desc(ReplyDraft.created_at),
        )
        .limit(limit)
    )
    if app_id:
        statement = statement.where(SteamReview.app_id == app_id)
    if status:
        statement = statement.where(ReplyDraft.status == status)

    result = await session.execute(statement)
    items: list[ReplyDraftAuditListItem] = []
    for draft, review, game, latest_reply in result.all():
        items.append(
            ReplyDraftAuditListItem(
                **draft_to_response(
                    draft,
                    fallback_error_message=(
                        latest_reply.error_message if latest_reply is not None else None
                    ),
                ),
                app_id=review.app_id,
                game_name=game.name,
                recommendation_id=review.recommendation_id,
                review_url=review.review_url,
                review_text=review.review_text,
                persona_name=review.persona_name,
                voted_up=review.voted_up,
                timestamp_created=review.timestamp_created,
            )
        )
    return items


@router.post("/{record_id}/delete-request", response_model=ReplyRecordResponse)
async def create_delete_request(
    record_id: int,
    request: DeleteRequestCreate,
    session: SessionDependency,
    current_user: RequireOperator,
) -> DeveloperReply:
    if not request.confirmed:
        raise HTTPException(status_code=400, detail="Delete request requires confirmation")

    record = await session.get(DeveloperReply, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Reply record not found")
    review = await session.get(SteamReview, record.review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    game = await session.get(SteamGame, review.app_id)
    if game is None or game.game_scope != "owned":
        raise HTTPException(status_code=403, detail="Competitor games do not support reply operations")

    record.delete_status = "requested"
    record.delete_request_reason = request.reason
    record.delete_requested_at = datetime.now(tz=CHINA_TZ)
    session.add(
        OperationLog(
            action="developer_reply_delete_requested",
            user_id=current_user.id,
            target_type="developer_reply",
            target_id=str(record.id),
            details=request.reason,
        )
    )
    await session.commit()
    await session.refresh(record)
    return record


def draft_to_response(
    draft: ReplyDraft,
    *,
    fallback_error_message: str | None = None,
) -> dict:
    return {
        "id": draft.id,
        "review_id": draft.review_id,
        "strategy_id": draft.strategy_id,
        "strategy_version": draft.strategy_version,
        "content": draft.content,
        "status": draft.status,
        "model_name": draft.model_name,
        "prompt_snapshot": draft.prompt_snapshot,
        "error_message": draft.error_message or fallback_error_message,
        "reviewed_at": draft.reviewed_at,
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
    }
