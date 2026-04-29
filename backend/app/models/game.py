from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.review import SteamReview


class SteamGame(TimestampMixin, Base):
    __tablename__ = "steam_games"

    app_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), index=True)
    release_date: Mapped[str | None] = mapped_column(String(80))
    price: Mapped[str | None] = mapped_column(String(80))
    developers: Mapped[list[str] | None] = mapped_column(JSON)
    publishers: Mapped[list[str] | None] = mapped_column(JSON)
    genres: Mapped[list[str] | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)

    reviews: Mapped[list[SteamReview]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
    )
