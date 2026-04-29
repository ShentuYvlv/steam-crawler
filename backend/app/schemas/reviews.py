from datetime import datetime

from pydantic import BaseModel, Field


class ReviewListItem(BaseModel):
    id: int
    app_id: int
    recommendation_id: str
    steam_id: str | None
    persona_name: str | None
    language: str | None
    review_text: str
    voted_up: bool | None
    votes_up: int
    votes_funny: int
    comment_count: int
    playtime_forever: float | None
    playtime_at_review: float | None
    timestamp_created: datetime | None
    sync_type: str
    processing_status: str
    reply_status: str

    model_config = {"from_attributes": True}


class ReviewDetailResponse(ReviewListItem):
    profile_url: str | None
    review_url: str | None
    weighted_vote_score: float | None
    steam_purchase: bool | None
    received_for_free: bool | None
    refunded: bool | None
    written_during_early_access: bool | None
    playtime_last_two_weeks: float | None
    num_games_owned: int | None
    num_reviews: int | None
    timestamp_updated: datetime | None
    last_played: datetime | None
    source_type: str
    developer_response: str | None
    developer_response_created_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReviewListResponse(BaseModel):
    items: list[ReviewListItem]
    total: int
    page: int
    page_size: int


class ReviewStatusUpdateRequest(BaseModel):
    processing_status: str | None = Field(default=None, min_length=1, max_length=50)
    reply_status: str | None = Field(default=None, min_length=1, max_length=50)


class BulkReviewStatusUpdateRequest(ReviewStatusUpdateRequest):
    review_ids: list[int] = Field(min_length=1, max_length=1000)


class ReviewStatusUpdateResponse(BaseModel):
    updated_count: int
