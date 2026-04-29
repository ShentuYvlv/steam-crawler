"""initial review admin schema

Revision ID: 20260429_0001
Revises:
Create Date: 2026-04-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260429_0001"
down_revision: str | None = None
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
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("external_user_id", sa.String(length=120), nullable=True),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        created_at_column(),
        updated_at_column(),
        sa.UniqueConstraint("external_user_id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"])

    op.create_table(
        "steam_games",
        sa.Column("app_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("release_date", sa.String(length=80), nullable=True),
        sa.Column("price", sa.String(length=80), nullable=True),
        sa.Column("developers", sa.JSON(), nullable=True),
        sa.Column("publishers", sa.JSON(), nullable=True),
        sa.Column("genres", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        created_at_column(),
        updated_at_column(),
    )
    op.create_index(op.f("ix_steam_games_name"), "steam_games", ["name"])

    op.create_table(
        "reply_strategies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        created_at_column(),
        updated_at_column(),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "steam_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("app_id", sa.Integer(), sa.ForeignKey("steam_games.app_id"), nullable=False),
        sa.Column("recommendation_id", sa.String(length=32), nullable=False),
        sa.Column("steam_id", sa.String(length=32), nullable=True),
        sa.Column("persona_name", sa.String(length=255), nullable=True),
        sa.Column("profile_url", sa.String(length=500), nullable=True),
        sa.Column("review_url", sa.String(length=500), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("review_text", sa.Text(), nullable=False),
        sa.Column("voted_up", sa.Boolean(), nullable=True),
        sa.Column("votes_up", sa.Integer(), nullable=False),
        sa.Column("votes_funny", sa.Integer(), nullable=False),
        sa.Column("weighted_vote_score", sa.Float(), nullable=True),
        sa.Column("comment_count", sa.Integer(), nullable=False),
        sa.Column("steam_purchase", sa.Boolean(), nullable=True),
        sa.Column("received_for_free", sa.Boolean(), nullable=True),
        sa.Column("refunded", sa.Boolean(), nullable=True),
        sa.Column("written_during_early_access", sa.Boolean(), nullable=True),
        sa.Column("playtime_forever", sa.Float(), nullable=True),
        sa.Column("playtime_at_review", sa.Float(), nullable=True),
        sa.Column("playtime_last_two_weeks", sa.Float(), nullable=True),
        sa.Column("num_games_owned", sa.Integer(), nullable=True),
        sa.Column("num_reviews", sa.Integer(), nullable=True),
        sa.Column("timestamp_created", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timestamp_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_played", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_type", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("processing_status", sa.String(length=50), nullable=False),
        sa.Column("reply_status", sa.String(length=50), nullable=False),
        sa.Column("developer_response", sa.Text(), nullable=True),
        sa.Column("developer_response_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.UniqueConstraint("recommendation_id", name="uq_steam_reviews_recommendation_id"),
    )
    op.create_index(op.f("ix_steam_reviews_language"), "steam_reviews", ["language"])
    op.create_index(op.f("ix_steam_reviews_steam_id"), "steam_reviews", ["steam_id"])
    op.create_index(
        op.f("ix_steam_reviews_timestamp_created"),
        "steam_reviews",
        ["timestamp_created"],
    )
    op.create_index(op.f("ix_steam_reviews_voted_up"), "steam_reviews", ["voted_up"])
    op.create_index(
        "ix_steam_reviews_app_created",
        "steam_reviews",
        ["app_id", "timestamp_created"],
    )
    op.create_index(
        "ix_steam_reviews_app_status",
        "steam_reviews",
        ["app_id", "processing_status", "reply_status"],
    )
    op.create_index("ix_steam_reviews_app_sync", "steam_reviews", ["app_id", "sync_type"])

    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("app_id", sa.Integer(), nullable=True),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("requested_limit", sa.Integer(), nullable=True),
        sa.Column("inserted_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        created_at_column(),
        updated_at_column(),
    )
    op.create_index(op.f("ix_sync_jobs_app_id"), "sync_jobs", ["app_id"])

    op.create_table(
        "operation_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=True),
        sa.Column("target_id", sa.String(length=80), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        created_at_column(),
        updated_at_column(),
    )
    op.create_index(op.f("ix_operation_logs_action"), "operation_logs", ["action"])

    op.create_table(
        "reply_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("steam_reviews.id"), nullable=False),
        sa.Column("strategy_id", sa.Integer(), sa.ForeignKey("reply_strategies.id"), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_snapshot", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        created_at_column(),
        updated_at_column(),
    )

    op.create_table(
        "developer_replies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("steam_reviews.id"), nullable=False),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("reply_drafts.id"), nullable=True),
        sa.Column("recommendation_id", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("steam_response", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        created_at_column(),
        updated_at_column(),
    )
    op.create_index(
        op.f("ix_developer_replies_recommendation_id"),
        "developer_replies",
        ["recommendation_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_developer_replies_recommendation_id"), table_name="developer_replies")
    op.drop_table("developer_replies")
    op.drop_table("reply_drafts")
    op.drop_index(op.f("ix_operation_logs_action"), table_name="operation_logs")
    op.drop_table("operation_logs")
    op.drop_index(op.f("ix_sync_jobs_app_id"), table_name="sync_jobs")
    op.drop_table("sync_jobs")
    op.drop_index("ix_steam_reviews_app_sync", table_name="steam_reviews")
    op.drop_index("ix_steam_reviews_app_status", table_name="steam_reviews")
    op.drop_index("ix_steam_reviews_app_created", table_name="steam_reviews")
    op.drop_index(op.f("ix_steam_reviews_voted_up"), table_name="steam_reviews")
    op.drop_index(op.f("ix_steam_reviews_timestamp_created"), table_name="steam_reviews")
    op.drop_index(op.f("ix_steam_reviews_steam_id"), table_name="steam_reviews")
    op.drop_index(op.f("ix_steam_reviews_language"), table_name="steam_reviews")
    op.drop_table("steam_reviews")
    op.drop_table("reply_strategies")
    op.drop_index(op.f("ix_steam_games_name"), table_name="steam_games")
    op.drop_table("steam_games")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
