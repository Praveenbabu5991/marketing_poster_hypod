"""Admin dashboard endpoints — margin, users, alerts, breakdowns.

All endpoints require ADMIN role (Cognito group) or allow-list membership.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.credit import CreditTransaction, UserCredits
from app.models.usage import UsageLog
from app.security.admin import require_admin
from app.security.models import UserDetails
from app.services.pricing import usd_cost_to_inr
from app.services.plans import PLANS

router = APIRouter()


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


@router.get("/overview")
async def overview(
    days: int = Query(30, ge=1, le=365),
    admin: UserDetails = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """High-level metrics over the last N days."""
    since_dt = _since(days)

    # API cost (USD) over period
    cost_usd = (
        (
            await db.execute(
                select(func.coalesce(func.sum(UsageLog.cost_usd), 0.0))
                .where(UsageLog.created_at >= since_dt)
                .where(UsageLog.refunded.is_(False))
            )
        ).scalar()
        or 0.0
    )
    cost_inr = usd_cost_to_inr(float(cost_usd))

    # Revenue (user-facing credits spent) over period — sum of negative deltas,
    # excluding signup bonuses / plan resets / refunds
    spend_credits = (
        (
            await db.execute(
                select(func.coalesce(func.sum(-CreditTransaction.delta), 0))
                .where(CreditTransaction.created_at >= since_dt)
                .where(CreditTransaction.delta < 0)
                .where(
                    CreditTransaction.reason.in_(["llm_call", "image_gen", "video_gen"])
                )
            )
        ).scalar()
        or 0
    )
    # 1 credit = ₹1
    revenue_inr = int(spend_credits)

    margin_pct = (
        round(((revenue_inr - cost_inr) / revenue_inr) * 100, 1)
        if revenue_inr > 0
        else 0.0
    )

    # Users by plan
    plan_rows = (
        await db.execute(
            select(UserCredits.plan, func.count())
            .group_by(UserCredits.plan)
        )
    ).all()
    user_count_by_plan = {p: c for p, c in plan_rows}

    # Top models by API cost
    model_rows = (
        await db.execute(
            select(
                UsageLog.model_name,
                func.coalesce(func.sum(UsageLog.cost_usd), 0.0).label("cost"),
                func.count().label("calls"),
            )
            .where(UsageLog.created_at >= since_dt)
            .group_by(UsageLog.model_name)
            .order_by(func.coalesce(func.sum(UsageLog.cost_usd), 0.0).desc())
            .limit(10)
        )
    ).all()
    top_models = [
        {
            "model": m,
            "cost_inr": usd_cost_to_inr(float(c)),
            "calls": calls,
        }
        for m, c, calls in model_rows
    ]

    # Loss-makers count: users whose API cost > their plan price this month
    loss_makers = 0
    wallets = (await db.execute(select(UserCredits))).scalars().all()
    for w in wallets:
        plan = PLANS.get(w.plan, {})
        price = plan.get("price_inr", 0)
        user_cost = (
            (
                await db.execute(
                    select(func.coalesce(func.sum(UsageLog.cost_usd), 0.0))
                    .where(UsageLog.user_id == w.user_id)
                    .where(UsageLog.created_at >= since_dt)
                )
            ).scalar()
            or 0.0
        )
        if price > 0 and usd_cost_to_inr(float(user_cost)) > price:
            loss_makers += 1

    return {
        "period_days": days,
        "revenue_inr": revenue_inr,
        "cost_inr": cost_inr,
        "margin_inr": revenue_inr - cost_inr,
        "margin_pct": margin_pct,
        "user_count_by_plan": user_count_by_plan,
        "top_models": top_models,
        "loss_makers_count": loss_makers,
    }


@router.get("/users")
async def list_users(
    plan: Optional[str] = Query(None),
    at_risk: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    days: int = Query(30, ge=1, le=365),
    admin: UserDetails = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List wallets + per-user cost/revenue for the window."""
    since_dt = _since(days)

    base = select(UserCredits)
    if plan:
        base = base.where(UserCredits.plan == plan)
    rows = (
        (
            await db.execute(base.limit(limit).offset(offset))
        )
        .scalars()
        .all()
    )

    users = []
    for w in rows:
        cost_usd = (
            (
                await db.execute(
                    select(func.coalesce(func.sum(UsageLog.cost_usd), 0.0))
                    .where(UsageLog.user_id == w.user_id)
                    .where(UsageLog.created_at >= since_dt)
                )
            ).scalar()
            or 0.0
        )
        rev = (
            (
                await db.execute(
                    select(func.coalesce(func.sum(-CreditTransaction.delta), 0))
                    .where(CreditTransaction.user_id == w.user_id)
                    .where(CreditTransaction.created_at >= since_dt)
                    .where(CreditTransaction.delta < 0)
                    .where(
                        CreditTransaction.reason.in_(
                            ["llm_call", "image_gen", "video_gen"]
                        )
                    )
                )
            ).scalar()
            or 0
        )
        cost_inr = usd_cost_to_inr(float(cost_usd))
        plan_price = PLANS.get(w.plan, {}).get("price_inr", 0)
        user_at_risk = plan_price > 0 and cost_inr > plan_price
        if at_risk and not user_at_risk:
            continue
        users.append(
            {
                "user_id": str(w.user_id),
                "plan": w.plan,
                "balance": w.balance,
                "monthly_allowance": w.monthly_allowance,
                "cost_inr": cost_inr,
                "revenue_inr": int(rev),
                "margin_inr": int(rev) - cost_inr,
                "at_risk": user_at_risk,
            }
        )

    return {"items": users, "limit": limit, "offset": offset, "days": days}


@router.get("/users/{user_id}")
async def user_detail(
    user_id: UUID,
    days: int = Query(30, ge=1, le=365),
    admin: UserDetails = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Detailed per-user view: wallet + usage breakdown by model/agent."""
    since_dt = _since(days)
    wallet = (
        await db.execute(select(UserCredits).where(UserCredits.user_id == user_id))
    ).scalar_one_or_none()
    if not wallet:
        raise HTTPException(404, "User wallet not found")

    # Usage breakdown by model
    model_rows = (
        await db.execute(
            select(
                UsageLog.model_name,
                UsageLog.action_type,
                func.count().label("calls"),
                func.coalesce(func.sum(UsageLog.cost_usd), 0.0).label("cost_usd"),
                func.coalesce(func.sum(UsageLog.credits_charged), 0).label("credits"),
            )
            .where(UsageLog.user_id == user_id)
            .where(UsageLog.created_at >= since_dt)
            .group_by(UsageLog.model_name, UsageLog.action_type)
        )
    ).all()

    by_model = [
        {
            "model": m,
            "action_type": a,
            "calls": calls,
            "cost_inr": usd_cost_to_inr(float(cost)),
            "credits_charged": int(credits),
        }
        for m, a, calls, cost, credits in model_rows
    ]

    # Recent transactions
    recent_tx = (
        (
            await db.execute(
                select(CreditTransaction)
                .where(CreditTransaction.user_id == user_id)
                .order_by(CreditTransaction.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )

    return {
        "user_id": str(wallet.user_id),
        "plan": wallet.plan,
        "balance": wallet.balance,
        "monthly_allowance": wallet.monthly_allowance,
        "resets_at": wallet.resets_at.isoformat() if wallet.resets_at else None,
        "stripe_customer_id": wallet.stripe_customer_id,
        "by_model": by_model,
        "recent_transactions": [
            {
                "id": str(t.id),
                "delta": t.delta,
                "balance_after": t.balance_after,
                "reason": t.reason,
                "created_at": t.created_at.isoformat(),
            }
            for t in recent_tx
        ],
    }


@router.get("/alerts")
async def alerts(
    days: int = Query(7, ge=1, le=90),
    admin: UserDetails = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Derived risk alerts for the admin dashboard."""
    since_dt = _since(days)
    alerts_out = []

    wallets = (await db.execute(select(UserCredits))).scalars().all()
    for w in wallets:
        cost_usd = (
            (
                await db.execute(
                    select(func.coalesce(func.sum(UsageLog.cost_usd), 0.0))
                    .where(UsageLog.user_id == w.user_id)
                    .where(UsageLog.created_at >= since_dt)
                )
            ).scalar()
            or 0.0
        )
        cost_inr = usd_cost_to_inr(float(cost_usd))
        plan_price = PLANS.get(w.plan, {}).get("price_inr", 0)
        if plan_price > 0 and cost_inr > plan_price:
            alerts_out.append(
                {
                    "user_id": str(w.user_id),
                    "plan": w.plan,
                    "cost_inr": cost_inr,
                    "plan_price": plan_price,
                    "severity": "high" if cost_inr > plan_price * 1.5 else "medium",
                    "type": "cost_exceeds_plan",
                    "message": f"User cost ₹{cost_inr:.0f} exceeds plan price ₹{plan_price}",
                }
            )
    return {"alerts": alerts_out, "period_days": days}
