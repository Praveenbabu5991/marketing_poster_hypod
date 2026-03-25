"""Add planner_session_id to calendar_plans.

Revision ID: 004
Revises: 003
Create Date: 2026-03-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "calendar_plans",
        sa.Column("planner_session_id", sa.Uuid(), sa.ForeignKey("sessions.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("calendar_plans", "planner_session_id")
