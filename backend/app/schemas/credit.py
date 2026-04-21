"""Pydantic schemas for credit wallet endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class BalanceResponse(BaseModel):
    user_id: UUID
    plan: str
    balance: int
    monthly_allowance: int
    resets_at: Optional[datetime]
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None


class EstimateResponse(BaseModel):
    action: str
    credits: int
    inr: int  # 1 credit = ₹1


class CreditTransactionOut(BaseModel):
    id: UUID
    delta: int
    balance_after: int
    reason: str
    usage_log_id: Optional[UUID]
    metadata_json: Optional[dict]
    created_at: datetime


class HistoryResponse(BaseModel):
    items: list[CreditTransactionOut]
    total: int
    limit: int
    offset: int


class TopUpRequest(BaseModel):
    user_id: UUID
    credits: int
    reason: str = "admin_topup"
    note: Optional[str] = None
