from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskScheduleBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    is_enabled: bool
    app_id: int = Field(gt=0)
    interval: str = Field(default="daily", pattern="^daily$")
    hour: int = Field(ge=0, le=23)
    options: dict[str, Any] = Field(default_factory=dict)


class TaskScheduleCreate(TaskScheduleBase):
    pass


class TaskScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_enabled: bool | None = None
    app_id: int | None = Field(default=None, gt=0)
    interval: str | None = Field(default=None, pattern="^daily$")
    hour: int | None = Field(default=None, ge=0, le=23)
    options: dict[str, Any] | None = None


class TaskScheduleResponse(BaseModel):
    id: int
    name: str
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
