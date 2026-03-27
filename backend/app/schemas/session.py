"""Pydantic schemas for session endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    brand_id: UUID
    agent_type: str = Field(..., max_length=50)


class SessionUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)


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
    # Calendar slot info (populated by list endpoint when session is linked to a slot)
    calendar_slot_date: Optional[str] = None
    calendar_slot_event: Optional[str] = None

    model_config = {"from_attributes": True}
