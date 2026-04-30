from datetime import datetime

from pydantic import BaseModel, Field


class ReplyDraftResponse(BaseModel):
    id: int
    review_id: int
    strategy_id: int | None
    strategy_version: int | None
    content: str
    status: str
    model_name: str | None
    prompt_snapshot: str | None
    error_message: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GenerateReplyResponse(BaseModel):
    draft: ReplyDraftResponse


class BulkGenerateReplyRequest(BaseModel):
    review_ids: list[int] = Field(min_length=1, max_length=1000)


class BulkGenerateReplyResponse(BaseModel):
    accepted_count: int
    review_ids: list[int]
