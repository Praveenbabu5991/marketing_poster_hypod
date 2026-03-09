"""Initial migration: brands and sessions tables.

Revision ID: 001
Revises: None
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column("tone", sa.String(50), nullable=False),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("products_services", sa.Text(), nullable=True),
        sa.Column("logo_path", sa.String(500), nullable=True),
        sa.Column("colors", postgresql.JSONB(), nullable=True, server_default="[]"),
        sa.Column("product_images", postgresql.JSONB(), nullable=True, server_default="[]"),
        sa.Column("style_reference_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_brands_user_id", "brands", ["user_id"])

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("thread_id", sa.String(255), unique=True, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_sessions_user_id", "sessions", ["user_id"])
    op.create_index("idx_sessions_brand_id", "sessions", ["brand_id"])


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("brands")
