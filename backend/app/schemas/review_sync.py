from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReviewSyncRequest(BaseModel):
    app_id: int = Field(gt=0)
    limit: int | None = Field(default=None, gt=0, le=10000)
    language: str = "schinese"
    filter: str = "recent"
    review_type: str = "all"
    purchase_type: str = "all"
    use_review_quality: bool = True
    per_page: int = Field(default=100, gt=0, le=100)


class ReviewSyncResponse(BaseModel):
    sync_job_id: int
    app_id: int
    inserted: int
    updated: int
    skipped: int
    status: str
    query_summary: dict[str, Any] = {}


class SyncJobListItem(BaseModel):
    id: int
    app_id: int | None
    job_type: str
    source_type: str
    status: str
    requested_limit: int | None
    inserted_count: int
    updated_count: int
    skipped_count: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SyncJobDetailResponse(SyncJobListItem):
    error_message: str | None
    updated_at: datetime


class TaskLogResponse(BaseModel):
    id: int
    task_id: int
    level: str
    message: str
    details: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SyncJobWithLogsResponse(SyncJobDetailResponse):
    logs: list[TaskLogResponse] = Field(default_factory=list)
