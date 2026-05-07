from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import SteamGame, SteamReview
from app.schemas import GameListItem

router = APIRouter(prefix="/games", tags=["games"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[GameListItem])
async def list_games_with_reviews(session: SessionDependency) -> list[GameListItem]:
    result = await session.execute(
        select(
            SteamGame.app_id,
            SteamGame.name,
            func.count(SteamReview.id).label("review_count"),
        )
        .join(SteamReview, SteamReview.app_id == SteamGame.app_id)
        .group_by(SteamGame.app_id, SteamGame.name)
        .order_by(desc(func.count(SteamReview.id)), SteamGame.app_id)
    )
    return [
        GameListItem(app_id=app_id, name=name, review_count=review_count)
        for app_id, name, review_count in result.all()
    ]
