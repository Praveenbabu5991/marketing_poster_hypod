"""Calendar plan endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.calendar import (
    CalendarPlanResponse,
    CalendarPlanUpdate,
    CalendarSlotResponse,
    CalendarSlotUpdate,
    SaveSlotsRequest,
)
from app.schemas.session import SessionCreate
from app.security.dependencies import require_authenticated_user
from app.security.models import UserDetails
from app.services import calendar_service, session_service

router = APIRouter()


@router.get("/plans", response_model=CalendarPlanResponse)
async def get_or_create_plan(
    brand_id: UUID = Query(...),
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Get existing plan for a month, or create a new draft."""
    plan = await calendar_service.get_or_create_plan(db, user.user_id, brand_id, year, month)
    slots = await calendar_service.get_slots(db, plan.id)
    return CalendarPlanResponse(
        id=plan.id,
        user_id=plan.user_id,
        brand_id=plan.brand_id,
        year=plan.year,
        month=plan.month,
        status=plan.status,
        planner_session_id=plan.planner_session_id,
        slots=[CalendarSlotResponse.model_validate(s) for s in slots],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.post("/plans/{plan_id}/slots", response_model=list[CalendarSlotResponse])
async def save_slots(
    plan_id: UUID,
    data: SaveSlotsRequest,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Save AI-generated slots to a plan (replaces existing slots)."""
    plan = await calendar_service.get_plan(db, plan_id, user.user_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    slots = await calendar_service.save_slots_from_agent(db, plan_id, data.slots)
    return [CalendarSlotResponse.model_validate(s) for s in slots]


@router.patch("/plans/{plan_id}", response_model=CalendarPlanResponse)
async def update_plan(
    plan_id: UUID,
    data: CalendarPlanUpdate,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Update plan-level fields (e.g. planner_session_id)."""
    plan = await calendar_service.update_plan(db, plan_id, user.user_id, data)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    slots = await calendar_service.get_slots(db, plan.id)
    return CalendarPlanResponse(
        id=plan.id,
        user_id=plan.user_id,
        brand_id=plan.brand_id,
        year=plan.year,
        month=plan.month,
        status=plan.status,
        planner_session_id=plan.planner_session_id,
        slots=[CalendarSlotResponse.model_validate(s) for s in slots],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.get("/plans/{plan_id}/slots", response_model=list[CalendarSlotResponse])
async def list_slots(
    plan_id: UUID,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """List all slots for a plan."""
    plan = await calendar_service.get_plan(db, plan_id, user.user_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    slots = await calendar_service.get_slots(db, plan_id)
    return [CalendarSlotResponse.model_validate(s) for s in slots]


@router.patch("/slots/{slot_id}", response_model=CalendarSlotResponse)
async def update_slot(
    slot_id: UUID,
    data: CalendarSlotUpdate,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a slot (approve, skip, edit idea, change type)."""
    slot = await calendar_service.update_slot(db, slot_id, user.user_id, data)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    return CalendarSlotResponse.model_validate(slot)


@router.post("/slots/{slot_id}/create-content", response_model=dict)
async def create_content_for_slot(
    slot_id: UUID,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a session for content generation and link it to the slot."""
    from sqlalchemy import select
    from app.models.calendar import CalendarSlot, CalendarPlan

    # Get slot and verify ownership
    result = await db.execute(select(CalendarSlot).where(CalendarSlot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    plan_result = await db.execute(
        select(CalendarPlan).where(CalendarPlan.id == slot.plan_id, CalendarPlan.user_id == user.user_id)
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Slot not found")

    # Create a session with the slot's agent type
    session_data = SessionCreate(brand_id=plan.brand_id, agent_type=slot.post_type)
    session = await session_service.create_session(db, user.user_id, session_data)

    # Link session to slot
    await calendar_service.link_session_to_slot(db, slot_id, session.id)

    return {
        "session_id": str(session.id),
        "slot_id": str(slot_id),
        "agent_type": slot.post_type,
        "post_idea": slot.post_idea,
    }
