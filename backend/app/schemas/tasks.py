from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskScheduleUpdate(BaseModel):
    is_enabled: bool
    app_id: int | None = Field(default=None, gt=0)
    interval: str = Field(default="hourly", pattern="^(hourly|daily)$")
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=0, ge=0, le=59)
    options: dict[str, Any] = {}


class TaskScheduleResponse(BaseModel):
    id: int
    task_type: str
    is_enabled: bool
    app_id: int | None
    interval: str
    hour: int | None
    minute: int | None
    options: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    jobs: list[Any]
    schedules: list[TaskScheduleResponse]
