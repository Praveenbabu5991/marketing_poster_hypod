"""Pydantic schemas for session endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    brand_id: UUID
    agent_type: str = Field(..., max_length=50)


class SessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    brand_id: UUID
    agent_type: str
    thread_id: str
    status: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
