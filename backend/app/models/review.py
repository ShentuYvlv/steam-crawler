from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.game import SteamGame
    from app.models.reply import DeveloperReply, ReplyDraft


class SteamReview(TimestampMixin, Base):
    __tablename__ = "steam_reviews"
    __table_args__ = (
        UniqueConstraint("recommendation_id", name="uq_steam_reviews_recommendation_id"),
        Index("ix_steam_reviews_app_created", "app_id", "timestamp_created"),
        Index("ix_steam_reviews_app_status", "app_id", "processing_status", "reply_status"),
        Index("ix_steam_reviews_app_sync", "app_id", "sync_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("steam_games.app_id"), nullable=False)
    recommendation_id: Mapped[str] = mapped_column(String(32), nullable=False)
    steam_id: Mapped[str | None] = mapped_column(String(32), index=True)
    persona_name: Mapped[str | None] = mapped_column(String(255))
    profile_url: Mapped[str | None] = mapped_column(String(500))
    review_url: Mapped[str | None] = mapped_column(String(500))
    language: Mapped[str | None] = mapped_column(String(32), index=True)
    review_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    voted_up: Mapped[bool | None] = mapped_column(Boolean, index=True)
    votes_up: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    votes_funny: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weighted_vote_score: Mapped[float | None] = mapped_column(Float)
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    steam_purchase: Mapped[bool | None] = mapped_column(Boolean)
    received_for_free: Mapped[bool | None] = mapped_column(Boolean)
    refunded: Mapped[bool | None] = mapped_column(Boolean)
    written_during_early_access: Mapped[bool | None] = mapped_column(Boolean)
    playtime_forever: Mapped[float | None] = mapped_column(Float)
    playtime_at_review: Mapped[float | None] = mapped_column(Float)
    playtime_last_two_weeks: Mapped[float | None] = mapped_column(Float)
    num_games_owned: Mapped[int | None] = mapped_column(Integer)
    num_reviews: Mapped[int | None] = mapped_column(Integer)
    timestamp_created: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    timestamp_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_played: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_type: Mapped[str] = mapped_column(String(32), default="incremental", nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default="steam_api", nullable=False)
    processing_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    reply_status: Mapped[str] = mapped_column(String(50), default="none", nullable=False)
    developer_response: Mapped[str | None] = mapped_column(Text)
    developer_response_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    game: Mapped[SteamGame] = relationship(back_populates="reviews")
    drafts: Mapped[list[ReplyDraft]] = relationship(
        back_populates="review",
        cascade="all, delete-orphan",
    )
    developer_replies: Mapped[list[DeveloperReply]] = relationship(
        back_populates="review",
        cascade="all, delete-orphan",
    )
