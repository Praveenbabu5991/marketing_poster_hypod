"""Usage analytics service — aggregation + paginated history."""

from datetime import date, datetime, time
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import UsageLog


async def get_usage_summary(
    db: AsyncSession,
    user_id: UUID,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    """Aggregate usage grouped by model_name + action_type.

    Returns:
        {
            "items": [
                {
                    "model_name": "...",
                    "action_type": "...",
                    "total_calls": N,
                    "successful_calls": N,
                    "failed_calls": N,
                    "total_prompt_tokens": N,
                    "total_completion_tokens": N,
                    "total_cost_usd": float,
                    "total_video_seconds": N,
                }
            ],
            "total_cost_usd": float,
        }
    """
    query = (
        select(
            UsageLog.model_name,
            UsageLog.action_type,
            func.count().label("total_calls"),
            func.count().filter(UsageLog.status == "success").label("successful_calls"),
            func.count().filter(UsageLog.status == "error").label("failed_calls"),
            func.coalesce(func.sum(UsageLog.prompt_tokens), 0).label("total_prompt_tokens"),
            func.coalesce(func.sum(UsageLog.completion_tokens), 0).label("total_completion_tokens"),
            func.coalesce(func.sum(UsageLog.cost_usd), 0.0).label("total_cost_usd"),
            func.coalesce(func.sum(UsageLog.video_duration_seconds), 0).label("total_video_seconds"),
        )
        .where(UsageLog.user_id == user_id)
        .group_by(UsageLog.model_name, UsageLog.action_type)
    )

    if start_date:
        query = query.where(UsageLog.created_at >= datetime.combine(start_date, time.min))
    if end_date:
        query = query.where(UsageLog.created_at <= datetime.combine(end_date, time.max))

    result = await db.execute(query)
    rows = result.all()

    items = []
    total_cost = 0.0
    for row in rows:
        item = {
            "model_name": row.model_name,
            "action_type": row.action_type,
            "total_calls": row.total_calls,
            "successful_calls": row.successful_calls,
            "failed_calls": row.failed_calls,
            "total_prompt_tokens": row.total_prompt_tokens,
            "total_completion_tokens": row.total_completion_tokens,
            "total_cost_usd": round(float(row.total_cost_usd), 6),
            "total_video_seconds": row.total_video_seconds,
        }
        items.append(item)
        total_cost += float(row.total_cost_usd)

    return {"items": items, "total_cost_usd": round(total_cost, 6)}


async def get_usage_history(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
    action_type: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Paginated raw usage logs.

    Returns:
        {
            "items": [...],
            "total": N,
            "limit": N,
            "offset": N,
        }
    """
    base = select(UsageLog).where(UsageLog.user_id == user_id)
    count_q = select(func.count()).select_from(UsageLog).where(UsageLog.user_id == user_id)

    if action_type:
        base = base.where(UsageLog.action_type == action_type)
        count_q = count_q.where(UsageLog.action_type == action_type)
    if model_name:
        base = base.where(UsageLog.model_name == model_name)
        count_q = count_q.where(UsageLog.model_name == model_name)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    query = base.order_by(UsageLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.scalars().all()

    items = []
    for row in rows:
        items.append({
            "id": str(row.id),
            "session_id": str(row.session_id) if row.session_id else None,
            "action_type": row.action_type,
            "model_name": row.model_name,
            "tool_name": row.tool_name,
            "status": row.status,
            "cost_usd": round(row.cost_usd, 6),
            "prompt_tokens": row.prompt_tokens,
            "completion_tokens": row.completion_tokens,
            "unit_count": row.unit_count,
            "video_duration_seconds": row.video_duration_seconds,
            "error_message": row.error_message,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })

    return {"items": items, "total": total, "limit": limit, "offset": offset}
