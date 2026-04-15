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
    posting_time: Optional[str] = None  # HH:MM 24h format
    dialogue: Optional[str] = None  # Video dialogue preview (ugc, creative_video only)


class CalendarSlotUpdate(BaseModel):
    event_name: Optional[str] = None
    event_type: Optional[str] = None
    post_idea: Optional[str] = None
    post_type: Optional[str] = None
    posting_time: Optional[str] = None
    status: Optional[str] = None
    metadata_json: Optional[dict] = None


class CalendarSlotResponse(BaseModel):
    id: UUID
    plan_id: UUID
    slot_date: date
    event_name: Optional[str]
    event_type: Optional[str]
    post_idea: Optional[str]
    post_type: str
    posting_time: Optional[str]
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
    planner_session_id: Optional[UUID] = None
    slots: list[CalendarSlotResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CalendarPlanUpdate(BaseModel):
    planner_session_id: Optional[UUID] = None


class SaveSlotsRequest(BaseModel):
    """Request body for saving AI-generated slots to a plan."""
    slots: list[CalendarSlotData]


class AddSlotRequest(BaseModel):
    """Request body for adding/upserting a single slot by date."""
    date: str  # ISO date string
    event_name: str = ""
    event_type: str = "regular"
    post_idea: str = ""
    post_type: str = "single_post"
    posting_time: Optional[str] = None
    status: str = "suggested"
    session_id: Optional[str] = None
    generated_image: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    dialogue: Optional[str] = None


class CreateContentRequest(BaseModel):
    """Request body for triggering content generation for a slot."""
    pass
