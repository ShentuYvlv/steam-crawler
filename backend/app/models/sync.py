from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin


class SyncJob(TimestampMixin, Base):
    __tablename__ = "sync_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("task_schedules.id", ondelete="SET NULL"),
        index=True,
    )
    schedule_name: Mapped[str | None] = mapped_column(String(255))
    trigger_type: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)
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
    logs: Mapped[list[TaskLog]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskLog.created_at",
    )
    schedule: Mapped[TaskSchedule | None] = relationship(back_populates="jobs")


class TaskSchedule(TimestampMixin, Base):
    __tablename__ = "task_schedules"
    __table_args__ = (
        UniqueConstraint("task_type", "app_id", name="uq_task_schedules_task_type_app_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    app_id: Mapped[int | None] = mapped_column(Integer)
    interval: Mapped[str] = mapped_column(String(50), default="daily", nullable=False)
    hour: Mapped[int | None] = mapped_column(Integer)
    minute: Mapped[int | None] = mapped_column(Integer)
    options: Mapped[dict | None] = mapped_column(JSON)
    jobs: Mapped[list[SyncJob]] = relationship(back_populates="schedule")


class TaskLog(TimestampMixin, Base):
    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("sync_jobs.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON)

    task: Mapped[SyncJob] = relationship(back_populates="logs")
