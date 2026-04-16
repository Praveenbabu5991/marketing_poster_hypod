"""Calendar plan CRUD business logic."""

import uuid
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar import CalendarPlan, CalendarSlot
from app.schemas.calendar import AddSlotRequest, CalendarPlanUpdate, CalendarSlotData, CalendarSlotUpdate


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


async def get_plan_by_planner_session(
    db: AsyncSession, session_id: UUID
) -> CalendarPlan | None:
    """Find the plan that uses a given session as its planner."""
    result = await db.execute(
        select(CalendarPlan).where(CalendarPlan.planner_session_id == session_id)
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
    """Bulk create CalendarSlots from agent output, replacing existing planner slots.

    Campaign slots (those with a session_id and status 'generated' or 'generating')
    are preserved — only non-campaign slots are deleted and replaced.
    """
    existing = await get_slots(db, plan_id)

    # Separate campaign slots (preserve) from planner slots (replace)
    # Also preserve metadata_json (duration, aspect_ratio, etc.) from existing slots
    campaign_statuses = {"generated", "generating"}
    kept_slots = []
    kept_dates: set[str] = set()
    existing_meta: dict[str, dict] = {}
    for slot in existing:
        date_str = slot.slot_date.isoformat()
        if slot.metadata_json:
            existing_meta[date_str] = dict(slot.metadata_json)
        if slot.session_id and slot.status in campaign_statuses:
            kept_slots.append(slot)
            kept_dates.add(date_str)
        else:
            await db.delete(slot)
    await db.flush()

    new_slots = list(kept_slots)
    for s in slots_data:
        # Skip dates already occupied by campaign slots
        if s.date in kept_dates:
            continue
        # Merge: preserve existing metadata (duration, aspect_ratio) + add dialogue
        metadata = existing_meta.get(s.date, {})
        if s.dialogue:
            metadata["dialogue"] = s.dialogue
        slot = CalendarSlot(
            plan_id=plan_id,
            slot_date=date.fromisoformat(s.date),
            event_name=s.event_name,
            event_type=s.event_type,
            post_idea=s.post_idea,
            post_type=s.post_type,
            posting_time=s.posting_time,
            status="suggested",
            metadata_json=metadata if metadata else None,
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


async def add_slot(
    db: AsyncSession, plan_id: UUID, user_id: UUID, data: AddSlotRequest
) -> CalendarSlot | None:
    """Add or update a single slot by date (upsert). Does NOT delete other slots."""
    # Verify user owns the plan
    plan_result = await db.execute(
        select(CalendarPlan).where(CalendarPlan.id == plan_id, CalendarPlan.user_id == user_id)
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        return None

    slot_date = date.fromisoformat(data.date)

    # Check if slot already exists for this date
    result = await db.execute(
        select(CalendarSlot).where(
            CalendarSlot.plan_id == plan_id,
            CalendarSlot.slot_date == slot_date,
        )
    )
    slot = result.scalar_one_or_none()

    if slot:
        # Update existing slot — overwrite fields when explicitly provided
        # (non-empty means the caller intended to set it; empty string = not provided)
        if data.event_name:
            slot.event_name = data.event_name
        if data.event_type:
            slot.event_type = data.event_type
        if data.post_idea:
            slot.post_idea = data.post_idea
        if data.post_type:
            slot.post_type = data.post_type
        if data.posting_time is not None:
            slot.posting_time = data.posting_time
        slot.status = data.status
        if data.session_id:
            slot.session_id = uuid.UUID(data.session_id)
        if data.generated_image:
            slot.generated_image = data.generated_image
        if data.caption:
            slot.caption = data.caption
        if data.hashtags:
            slot.hashtags = data.hashtags
        # Update metadata_json — merge incoming metadata + dialogue into existing
        # Use a new dict so SQLAlchemy detects the change (mutable JSON tracking)
        new_meta = dict(slot.metadata_json) if slot.metadata_json else {}
        if data.metadata_json:
            new_meta.update(data.metadata_json)
        if data.dialogue is not None:
            new_meta["dialogue"] = data.dialogue
        if new_meta:
            slot.metadata_json = new_meta
        slot.updated_at = datetime.now(timezone.utc)
    else:
        # Create new slot
        metadata = dict(data.metadata_json) if data.metadata_json else {}
        if data.dialogue:
            metadata["dialogue"] = data.dialogue
        slot = CalendarSlot(
            plan_id=plan_id,
            slot_date=slot_date,
            event_name=data.event_name,
            event_type=data.event_type,
            post_idea=data.post_idea,
            post_type=data.post_type,
            posting_time=data.posting_time,
            status=data.status,
            metadata_json=metadata if metadata else None,
        )
        if data.session_id:
            slot.session_id = uuid.UUID(data.session_id)
        if data.generated_image:
            slot.generated_image = data.generated_image
        if data.caption:
            slot.caption = data.caption
        if data.hashtags:
            slot.hashtags = data.hashtags
        db.add(slot)

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
