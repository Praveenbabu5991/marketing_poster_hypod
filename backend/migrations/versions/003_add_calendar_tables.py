"""Add calendar_plans and calendar_slots tables.

Revision ID: 003
Revises: 002
Create Date: 2026-03-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calendar_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("brand_id", sa.Uuid(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "brand_id", "year", "month", name="uq_plan_user_brand_month"),
    )
    op.create_index(op.f("ix_calendar_plans_user_id"), "calendar_plans", ["user_id"])
    op.create_index(op.f("ix_calendar_plans_brand_id"), "calendar_plans", ["brand_id"])

    op.create_table(
        "calendar_slots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("calendar_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slot_date", sa.Date(), nullable=False),
        sa.Column("event_name", sa.String(200), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=True),
        sa.Column("post_idea", sa.Text(), nullable=True),
        sa.Column("post_type", sa.String(50), nullable=False, server_default="single_post"),
        sa.Column("status", sa.String(20), nullable=False, server_default="suggested"),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id"), nullable=True),
        sa.Column("generated_image", sa.String(500), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("hashtags", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(op.f("ix_calendar_slots_plan_id"), "calendar_slots", ["plan_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_calendar_slots_plan_id"), table_name="calendar_slots")
    op.drop_table("calendar_slots")
    op.drop_index(op.f("ix_calendar_plans_brand_id"), table_name="calendar_plans")
    op.drop_index(op.f("ix_calendar_plans_user_id"), table_name="calendar_plans")
    op.drop_table("calendar_plans")
