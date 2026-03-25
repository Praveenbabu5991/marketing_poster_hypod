"""Calendar plan CRUD business logic."""

import uuid
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar import CalendarPlan, CalendarSlot
from app.schemas.calendar import CalendarPlanUpdate, CalendarSlotData, CalendarSlotUpdate


async def get_or_create_plan(
    db: AsyncSession, user_id: UUID, brand_id: UUID, year: int, month: int
) -> CalendarPlan:
    """Get existing plan or create a new draft plan for the given month."""
    result = await db.execute(
        select(CalendarPlan).where(
            CalendarPlan.user_id == user_id,
            CalendarPlan.brand_id == brand_id,
            CalendarPlan.year == year,
            CalendarPlan.month == month,
        )
    )
    plan = result.scalar_one_or_none()
    if plan:
        return plan

    plan = CalendarPlan(
        user_id=user_id,
        brand_id=brand_id,
        year=year,
        month=month,
        status="draft",
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return plan


async def get_plan(db: AsyncSession, plan_id: UUID, user_id: UUID) -> CalendarPlan | None:
    result = await db.execute(
        select(CalendarPlan).where(CalendarPlan.id == plan_id, CalendarPlan.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_plan_for_month(
    db: AsyncSession, user_id: UUID, brand_id: UUID, year: int, month: int
) -> CalendarPlan | None:
    result = await db.execute(
        select(CalendarPlan).where(
            CalendarPlan.user_id == user_id,
            CalendarPlan.brand_id == brand_id,
            CalendarPlan.year == year,
            CalendarPlan.month == month,
        )
    )
    return result.scalar_one_or_none()


async def update_plan(
    db: AsyncSession, plan_id: UUID, user_id: UUID, data: CalendarPlanUpdate
) -> CalendarPlan | None:
    """Update plan-level fields (e.g. planner_session_id)."""
    result = await db.execute(
        select(CalendarPlan).where(CalendarPlan.id == plan_id, CalendarPlan.user_id == user_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plan, key, value)
    plan.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(plan)
    return plan


async def get_slots(db: AsyncSession, plan_id: UUID) -> list[CalendarSlot]:
    result = await db.execute(
        select(CalendarSlot)
        .where(CalendarSlot.plan_id == plan_id)
        .order_by(CalendarSlot.slot_date)
    )
    return list(result.scalars().all())


async def save_slots_from_agent(
    db: AsyncSession, plan_id: UUID, slots_data: list[CalendarSlotData]
) -> list[CalendarSlot]:
    """Bulk create CalendarSlots from agent output, replacing existing slots."""
    # Delete existing slots for this plan
    existing = await get_slots(db, plan_id)
    for slot in existing:
        await db.delete(slot)
    await db.flush()

    new_slots = []
    for s in slots_data:
        slot = CalendarSlot(
            plan_id=plan_id,
            slot_date=date.fromisoformat(s.date),
            event_name=s.event_name,
            event_type=s.event_type,
            post_idea=s.post_idea,
            post_type=s.post_type,
            posting_time=s.posting_time,
            status="suggested",
        )
        db.add(slot)
        new_slots.append(slot)

    # Update plan status to active
    plan_result = await db.execute(select(CalendarPlan).where(CalendarPlan.id == plan_id))
    plan = plan_result.scalar_one_or_none()
    if plan:
        plan.status = "active"
        plan.updated_at = datetime.now(timezone.utc)

    await db.flush()
    for slot in new_slots:
        await db.refresh(slot)
    return new_slots


async def update_slot(
    db: AsyncSession, slot_id: UUID, user_id: UUID, data: CalendarSlotUpdate
) -> CalendarSlot | None:
    """Update a slot, verifying ownership via the plan."""
    result = await db.execute(select(CalendarSlot).where(CalendarSlot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        return None

    # Verify user owns the plan
    plan_result = await db.execute(
        select(CalendarPlan).where(CalendarPlan.id == slot.plan_id, CalendarPlan.user_id == user_id)
    )
    if not plan_result.scalar_one_or_none():
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(slot, key, value)
    slot.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(slot)
    return slot


async def link_session_to_slot(
    db: AsyncSession,
    slot_id: UUID,
    session_id: UUID,
    image_path: str | None = None,
    caption: str | None = None,
    hashtags: str | None = None,
) -> CalendarSlot | None:
    """Update a slot after content generation."""
    result = await db.execute(select(CalendarSlot).where(CalendarSlot.id == slot_id))
    slot = result.scalar_one_or_none()
    if not slot:
        return None

    slot.session_id = session_id
    slot.status = "generating"
    if image_path:
        slot.generated_image = image_path
        slot.status = "generated"
    if caption:
        slot.caption = caption
    if hashtags:
        slot.hashtags = hashtags
    slot.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(slot)
    return slot
