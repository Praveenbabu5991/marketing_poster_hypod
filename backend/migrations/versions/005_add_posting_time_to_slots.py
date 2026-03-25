"""Add posting_time to calendar_slots.

Revision ID: 005
Revises: 004
Create Date: 2026-03-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "calendar_slots",
        sa.Column("posting_time", sa.String(5), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("calendar_slots", "posting_time")
