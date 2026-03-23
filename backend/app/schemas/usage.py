"""Pydantic schemas for usage endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class UsageSummaryItem(BaseModel):
    model_name: str
    action_type: str
    total_calls: int
    successful_calls: int
    failed_calls: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost_usd: float
    total_video_seconds: int


class UsageSummaryResponse(BaseModel):
    items: list[UsageSummaryItem]
    total_cost_usd: float


class UsageLogItem(BaseModel):
    id: str
    session_id: Optional[str] = None
    action_type: str
    model_name: str
    tool_name: Optional[str] = None
    status: str
    cost_usd: float
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    unit_count: int
    video_duration_seconds: Optional[int] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None


class UsageHistoryResponse(BaseModel):
    items: list[UsageLogItem]
    total: int
    limit: int
    offset: int
