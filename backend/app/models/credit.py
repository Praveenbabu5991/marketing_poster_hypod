"""Credit wallet models: UserCredits (balance) + CreditTransaction (audit log)."""

import uuid
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, ForeignKey, Uuid, JSON
from sqlalchemy.sql import func
from app.database import Base


class UserCredits(Base):
    """Per-user credit wallet. One row per user."""
    __tablename__ = "user_credits"

    user_id = Column(Uuid, primary_key=True)
    plan = Column(String(50), nullable=False, default="free")
    balance = Column(Integer, nullable=False, default=0)
    monthly_allowance = Column(Integer, nullable=False, default=0)
    resets_at = Column(DateTime(timezone=True), nullable=True)

    # Stripe scaffolding (populated in Phase 3 / real integration later)
    stripe_customer_id = Column(String(120), nullable=True)
    stripe_subscription_id = Column(String(120), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CreditTransaction(Base):
    """Audit log — one row per wallet change (spend / refund / top-up / reset)."""
    __tablename__ = "credit_transactions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, nullable=False, index=True)

    # Signed delta: negative = spend, positive = top-up/refund
    delta = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)

    # "llm_call" | "image_gen" | "video_gen" | "refund" | "plan_reset"
    # | "stripe_topup" | "admin_topup" | "signup_bonus"
    reason = Column(String(50), nullable=False, index=True)

    # FK to usage_logs when the transaction is tied to an API call
    usage_log_id = Column(Uuid, ForeignKey("usage_logs.id"), nullable=True)

    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
