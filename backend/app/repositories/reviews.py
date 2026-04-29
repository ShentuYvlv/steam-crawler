from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SteamGame, SteamReview


@dataclass(frozen=True)
class ReviewUpsertResult:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0


class SteamReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_game(self, app_id: int, name: str | None = None) -> SteamGame:
        game = await self.session.get(SteamGame, app_id)
        if game is None:
            game = SteamGame(app_id=app_id, name=name)
            self.session.add(game)
            await self.session.flush()
        elif name and not game.name:
            game.name = name
        return game

    async def upsert_review(self, values: dict[str, Any]) -> ReviewUpsertResult:
        recommendation_id = str(values.get("recommendation_id") or "").strip()
        app_id = values.get("app_id")
        if not recommendation_id or app_id is None:
            return ReviewUpsertResult(skipped=1)

        await self.ensure_game(int(app_id))

        existing = await self.get_by_recommendation_id(recommendation_id)
        if existing is None:
            self.session.add(SteamReview(**values))
            await self.session.flush()
            return ReviewUpsertResult(inserted=1)

        for key, value in values.items():
            if key in {"id", "recommendation_id", "created_at"}:
                continue
            setattr(existing, key, value)
        await self.session.flush()
        return ReviewUpsertResult(updated=1)

    async def get_by_recommendation_id(self, recommendation_id: str) -> SteamReview | None:
        result = await self.session.execute(
            select(SteamReview).where(SteamReview.recommendation_id == recommendation_id)
        )
        return result.scalar_one_or_none()
