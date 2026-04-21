"""Add credit wallet tables + credits_charged/refunded on usage_logs.

Revision ID: 007
Revises: 006
Create Date: 2026-04-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # user_credits — per-user wallet
    op.create_table(
        "user_credits",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("plan", sa.String(length=50), nullable=False, server_default="free"),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("monthly_allowance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resets_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stripe_customer_id", sa.String(length=120), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # credit_transactions — audit log
    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("usage_log_id", sa.Uuid(), sa.ForeignKey("usage_logs.id"), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_credit_transactions_user_id", "credit_transactions", ["user_id"]
    )
    op.create_index(
        "ix_credit_transactions_reason", "credit_transactions", ["reason"]
    )
    op.create_index(
        "ix_credit_transactions_created_at", "credit_transactions", ["created_at"]
    )

    # usage_logs — add credits_charged + refunded
    op.add_column(
        "usage_logs",
        sa.Column(
            "credits_charged", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "usage_logs",
        sa.Column(
            "refunded", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("usage_logs", "refunded")
    op.drop_column("usage_logs", "credits_charged")
    op.drop_index("ix_credit_transactions_created_at", table_name="credit_transactions")
    op.drop_index("ix_credit_transactions_reason", table_name="credit_transactions")
    op.drop_index("ix_credit_transactions_user_id", table_name="credit_transactions")
    op.drop_table("credit_transactions")
    op.drop_table("user_credits")
