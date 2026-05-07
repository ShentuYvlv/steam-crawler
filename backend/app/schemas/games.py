from pydantic import BaseModel


class GameListItem(BaseModel):
    app_id: int
    name: str | None
    review_count: int
