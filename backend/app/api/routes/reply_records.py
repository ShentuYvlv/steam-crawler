from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import RequireOperator
from app.models import DeveloperReply, OperationLog, SteamReview
from app.schemas import DeleteRequestCreate, ReplyRecordListItem, ReplyRecordResponse

router = APIRouter(prefix="/reply-records", tags=["reply-records"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CHINA_TZ = ZoneInfo("Asia/Shanghai")


@router.get("", response_model=list[ReplyRecordListItem])
async def list_reply_records(
    session: SessionDependency,
    status: str | None = None,
    limit: int = Query(default=50, gt=0, le=200),
) -> list[ReplyRecordListItem]:
    statement = (
        select(DeveloperReply, SteamReview)
        .join(SteamReview, SteamReview.id == DeveloperReply.review_id)
        .order_by(desc(DeveloperReply.created_at), desc(DeveloperReply.id))
        .limit(limit)
    )
    if status:
        statement = statement.where(DeveloperReply.status == status)

    result = await session.execute(statement)
    items: list[ReplyRecordListItem] = []
    for record, review in result.all():
        items.append(
            ReplyRecordListItem(
                **ReplyRecordResponse.model_validate(record).model_dump(),
                app_id=review.app_id,
                review_text=review.review_text,
                persona_name=review.persona_name,
                voted_up=review.voted_up,
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
