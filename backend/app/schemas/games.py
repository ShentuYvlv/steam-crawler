from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GameListItem(BaseModel):
    app_id: int
    name: str | None
    game_scope: str
    review_count: int
    has_schedule: bool = False
    schedule_id: int | None = None
    schedule_name: str | None = None
    schedule_enabled: bool = False
    schedule_hour: int | None = None
    schedule_options: dict[str, Any] | None = None
    latest_task_id: int | None = None
    latest_task_status: str | None = None
    latest_task_finished_at: datetime | None = None


class GameSyncOptionsPayload(BaseModel):
    enabled: bool = False
    hour: int = Field(default=0, ge=0, le=23)
    language: str = "schinese"
    filter: str = "recent"
    review_type: str = "all"
    purchase_type: str = "all"
    use_review_quality: bool = True
    per_page: int = Field(default=100, gt=0, le=100)

    def to_schedule_options(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "filter": self.filter,
            "review_type": self.review_type,
            "purchase_type": self.purchase_type,
            "use_review_quality": self.use_review_quality,
            "per_page": self.per_page,
        }


class GameCreateRequest(BaseModel):
    app_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=255)
    game_scope: str = Field(default="competitor", pattern="^(owned|competitor)$")
    sync: GameSyncOptionsPayload | None = None


class GameUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    game_scope: str = Field(default="competitor", pattern="^(owned|competitor)$")
    sync: GameSyncOptionsPayload | None = None


class GameSyncBatchResponse(BaseModel):
    accepted_count: int
    task_ids: list[int] = Field(default_factory=list)
