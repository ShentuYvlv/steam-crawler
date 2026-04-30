from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import ReplyDraft
from app.schemas import ReplyDraftResponse, ReplyDraftUpdate

router = APIRouter(prefix="/reply-drafts", tags=["reply-drafts"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/{draft_id}", response_model=ReplyDraftResponse)
async def get_reply_draft(
    draft_id: int,
    session: SessionDependency,
) -> ReplyDraft:
    draft = await session.get(ReplyDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Reply draft not found")
    return draft


@router.patch("/{draft_id}", response_model=ReplyDraftResponse)
async def update_reply_draft(
    draft_id: int,
    request: ReplyDraftUpdate,
    session: SessionDependency,
) -> ReplyDraft:
    draft = await session.get(ReplyDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Reply draft not found")

    if request.content is not None:
        draft.content = request.content
    if request.status is not None:
        draft.status = request.status
    await session.commit()
    await session.refresh(draft)
    return draft
