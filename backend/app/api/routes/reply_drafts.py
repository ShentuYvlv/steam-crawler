from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import RequireOperator
from app.models import ReplyDraft, SteamGame, SteamReview
from app.schemas import ReplyDraftResponse, ReplyDraftUpdate

router = APIRouter(prefix="/reply-drafts", tags=["reply-drafts"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CHINA_TZ = ZoneInfo("Asia/Shanghai")


@router.get("/{draft_id}", response_model=ReplyDraftResponse)
async def get_reply_draft(
    draft_id: int,
    session: SessionDependency,
) -> ReplyDraft:
    draft = await session.get(ReplyDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Reply draft not found")
    await _ensure_draft_is_owned(session, draft)
    return draft


@router.patch("/{draft_id}", response_model=ReplyDraftResponse)
async def update_reply_draft(
    draft_id: int,
    request: ReplyDraftUpdate,
    session: SessionDependency,
    current_user: RequireOperator,
) -> ReplyDraft:
    draft = await session.get(ReplyDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Reply draft not found")
    await _ensure_draft_is_owned(session, draft)

    if request.content is not None:
        draft.content = request.content
    if request.status is not None:
        draft.status = request.status
        review = await session.get(SteamReview, draft.review_id)
        if request.status == "rejected":
            now = datetime.now(tz=CHINA_TZ)
            draft.reviewed_by_user_id = current_user.id
            draft.reviewed_at = now
            if review is not None:
                review.reply_status = "rejected"
        elif request.status == "pending_review" and review is not None:
            review.reply_status = "drafted"
    await session.commit()
    await session.refresh(draft)
    return draft


async def _ensure_draft_is_owned(session: AsyncSession, draft: ReplyDraft) -> None:
    result = await session.execute(
        select(SteamGame.game_scope)
        .select_from(SteamReview)
        .join(SteamGame, SteamGame.app_id == SteamReview.app_id)
        .where(SteamReview.id == draft.review_id)
        .limit(1)
    )
    game_scope = result.scalar_one_or_none()
    if game_scope != "owned":
        raise HTTPException(status_code=403, detail="Competitor games do not support reply operations")
