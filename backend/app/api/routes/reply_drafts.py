from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import ReplyDraft
from app.schemas import ReplyDraftResponse

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
