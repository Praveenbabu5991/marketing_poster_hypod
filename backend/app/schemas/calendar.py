"""Pydantic schemas for calendar endpoints."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CalendarSlotData(BaseModel):
    """Slot data as received from the AI agent."""
    date: str  # ISO date string
    event_name: str = ""
    event_type: str = "regular"
    post_idea: str = ""
    post_type: str = "single_post"


class CalendarSlotUpdate(BaseModel):
    event_name: Optional[str] = None
    event_type: Optional[str] = None
    post_idea: Optional[str] = None
    post_type: Optional[str] = None
    status: Optional[str] = None


class CalendarSlotResponse(BaseModel):
    id: UUID
    plan_id: UUID
    slot_date: date
    event_name: Optional[str]
    event_type: Optional[str]
    post_idea: Optional[str]
    post_type: str
    status: str
    session_id: Optional[UUID]
    generated_image: Optional[str]
    caption: Optional[str]
    hashtags: Optional[str]
    metadata_json: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CalendarPlanResponse(BaseModel):
    id: UUID
    user_id: UUID
    brand_id: UUID
    year: int
    month: int
    status: str
    slots: list[CalendarSlotResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SaveSlotsRequest(BaseModel):
    """Request body for saving AI-generated slots to a plan."""
    slots: list[CalendarSlotData]


class CreateContentRequest(BaseModel):
    """Request body for triggering content generation for a slot."""
    pass
