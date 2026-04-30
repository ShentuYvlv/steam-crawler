from datetime import date

from pydantic import BaseModel


class StatsOverviewResponse(BaseModel):
    total_reviews: int
    positive_reviews: int
    negative_reviews: int
    replied_reviews: int
    pending_reviews: int
    ignored_reviews: int
    positive_rate: float
    reply_success_rate: float


class StatsTimeseriesItem(BaseModel):
    date: date
    new_reviews: int
    sent_replies: int


class StatsTimeseriesResponse(BaseModel):
    items: list[StatsTimeseriesItem]
