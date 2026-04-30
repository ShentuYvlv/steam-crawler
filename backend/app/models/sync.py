from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin


class SyncJob(TimestampMixin, Base):
    __tablename__ = "sync_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_id: Mapped[int | None] = mapped_column(Integer, index=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    requested_limit: Mapped[int | None] = mapped_column(Integer)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskSchedule(TimestampMixin, Base):
    __tablename__ = "task_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_type: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    app_id: Mapped[int | None] = mapped_column(Integer)
    interval: Mapped[str] = mapped_column(String(50), default="hourly", nullable=False)
    hour: Mapped[int | None] = mapped_column(Integer)
    minute: Mapped[int | None] = mapped_column(Integer)
    options: Mapped[dict | None] = mapped_column(JSON)


class TaskLog(TimestampMixin, Base):
    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("sync_jobs.id"), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON)
