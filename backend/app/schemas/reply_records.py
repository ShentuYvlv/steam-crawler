from datetime import datetime

from pydantic import BaseModel, Field


class SendReplyRequest(BaseModel):
    draft_id: int | None = None
    content: str | None = Field(default=None, min_length=1)
    confirmed: bool = False


class BulkSendReplyRequest(BaseModel):
    review_ids: list[int] = Field(min_length=1, max_length=100)
    confirmed: bool = False


class ReplyRecordResponse(BaseModel):
    id: int
    review_id: int
    draft_id: int | None
    recommendation_id: str
    content: str
    status: str
    steam_response: str | None
    error_message: str | None
    sent_at: datetime | None
    delete_status: str
    delete_request_reason: str | None
    delete_requested_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReplyRecordListItem(ReplyRecordResponse):
    app_id: int
    review_text: str
    persona_name: str | None
    voted_up: bool | None


class SendReplyResponse(BaseModel):
    record: ReplyRecordResponse


class BulkSendReplyResponse(BaseModel):
    accepted_count: int
    review_ids: list[int]


class DeleteRequestCreate(BaseModel):
    confirmed: bool = False
    reason: str | None = Field(default=None, max_length=1000)
