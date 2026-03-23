"""Rebuild usage_logs: drop enum, add cost/status/tool tracking.

Revision ID: 002
Revises: 45b1cf72f89d
Create Date: 2026-03-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "45b1cf72f89d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old table and enum
    op.drop_index(op.f("ix_usage_logs_user_id"), table_name="usage_logs")
    op.drop_index(op.f("ix_usage_logs_model_name"), table_name="usage_logs")
    op.drop_index(op.f("ix_usage_logs_created_at"), table_name="usage_logs")
    op.drop_index(op.f("ix_usage_logs_action_type"), table_name="usage_logs")
    op.drop_table("usage_logs")

    # Drop the stale enum type
    op.execute("DROP TYPE IF EXISTS aimodelname_enum")

    # Recreate with new schema
    op.create_table(
        "usage_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id"), nullable=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("unit_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("video_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(op.f("ix_usage_logs_user_id"), "usage_logs", ["user_id"])
    op.create_index(op.f("ix_usage_logs_model_name"), "usage_logs", ["model_name"])
    op.create_index(op.f("ix_usage_logs_action_type"), "usage_logs", ["action_type"])
    op.create_index(op.f("ix_usage_logs_created_at"), "usage_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_usage_logs_user_id"), table_name="usage_logs")
    op.drop_index(op.f("ix_usage_logs_model_name"), table_name="usage_logs")
    op.drop_index(op.f("ix_usage_logs_created_at"), table_name="usage_logs")
    op.drop_index(op.f("ix_usage_logs_action_type"), table_name="usage_logs")
    op.drop_table("usage_logs")
