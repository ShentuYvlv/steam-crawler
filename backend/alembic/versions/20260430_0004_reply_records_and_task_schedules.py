"""reply records delete request and task schedules

Revision ID: 20260430_0004
Revises: 20260430_0003
Create Date: 2026-04-30 00:04:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260430_0004"
down_revision: str | None = "20260430_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def created_at_column() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def updated_at_column() -> sa.Column:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def upgrade() -> None:
    op.add_column(
        "developer_replies",
        sa.Column("delete_status", sa.String(length=50), nullable=False, server_default="none"),
    )
    op.add_column("developer_replies", sa.Column("delete_request_reason", sa.Text(), nullable=True))
    op.add_column(
        "developer_replies",
        sa.Column("delete_requested_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "task_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("app_id", sa.Integer(), nullable=True),
        sa.Column("interval", sa.String(length=50), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=True),
        sa.Column("minute", sa.Integer(), nullable=True),
        sa.Column("options", sa.JSON(), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.UniqueConstraint("task_type"),
    )
    op.create_index(op.f("ix_task_schedules_task_type"), "task_schedules", ["task_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_task_schedules_task_type"), table_name="task_schedules")
    op.drop_table("task_schedules")
    op.drop_column("developer_replies", "delete_requested_at")
    op.drop_column("developer_replies", "delete_request_reason")
    op.drop_column("developer_replies", "delete_status")
