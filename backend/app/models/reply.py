from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.review import SteamReview


class ReplyStrategy(TimestampMixin, Base):
    __tablename__ = "reply_strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    reply_rules: Mapped[str | None] = mapped_column(Text)
    forbidden_terms: Mapped[list[str] | None] = mapped_column(JSON)
    good_examples: Mapped[list[dict] | None] = mapped_column(JSON)
    brand_voice: Mapped[str | None] = mapped_column(Text)
    classification_strategy: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), default="qwen-plus", nullable=False)
    temperature: Mapped[float | None]
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class ReplyDraft(TimestampMixin, Base):
    __tablename__ = "reply_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("steam_reviews.id"), nullable=False)
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("reply_strategies.id"))
    strategy_version: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(120))
    prompt_snapshot: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    review: Mapped[SteamReview] = relationship(back_populates="drafts")


class DeveloperReply(TimestampMixin, Base):
    __tablename__ = "developer_replies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("steam_reviews.id"), nullable=False)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("reply_drafts.id"))
    recommendation_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    steam_response: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    delete_status: Mapped[str] = mapped_column(String(50), default="none", nullable=False)
    delete_request_reason: Mapped[str | None] = mapped_column(Text)
    delete_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    review: Mapped[SteamReview] = relationship(back_populates="developer_replies")
