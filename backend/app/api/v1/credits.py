"""Credit wallet endpoints — balance, estimate, transaction history."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.credit import CreditTransaction
from app.schemas.credit import (
    BalanceResponse,
    CreditTransactionOut,
    EstimateResponse,
    HistoryResponse,
)
from app.security.dependencies import require_authenticated_user
from app.security.models import UserDetails
from app.services import credit_service
from app.services.pricing import estimate_credits

router = APIRouter()


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's credit wallet (creates on first call)."""
    wallet = await credit_service.get_balance(db, user.user_id)
    return BalanceResponse(
        user_id=wallet.user_id,
        plan=wallet.plan,
        balance=wallet.balance,
        monthly_allowance=wallet.monthly_allowance,
        resets_at=wallet.resets_at,
        stripe_customer_id=wallet.stripe_customer_id,
        stripe_subscription_id=wallet.stripe_subscription_id,
    )


@router.get("/estimate", response_model=EstimateResponse)
async def estimate(
    action: str = Query(..., description="llm_text | image | video | search"),
    duration_sec: Optional[int] = Query(None, description="For video actions"),
    user: UserDetails = Depends(require_authenticated_user),
):
    """Return the credit cost for a given user-facing action.

    Used by the frontend to show cost preview before an expensive click.
    """
    valid = {"llm_text", "image", "video", "search"}
    if action not in valid:
        raise HTTPException(400, f"action must be one of {valid}")
    credits = estimate_credits(action, duration_sec=duration_sec)
    return EstimateResponse(action=action, credits=credits, inr=credits)


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    reason: Optional[str] = Query(None),
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Paginated audit log of the user's own credit transactions."""
    base = select(CreditTransaction).where(CreditTransaction.user_id == user.user_id)
    count_q = select(func.count()).select_from(CreditTransaction).where(
        CreditTransaction.user_id == user.user_id
    )
    if reason:
        base = base.where(CreditTransaction.reason == reason)
        count_q = count_q.where(CreditTransaction.reason == reason)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (
        (
            await db.execute(
                base.order_by(CreditTransaction.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )

    return HistoryResponse(
        items=[
            CreditTransactionOut(
                id=r.id,
                delta=r.delta,
                balance_after=r.balance_after,
                reason=r.reason,
                usage_log_id=r.usage_log_id,
                metadata_json=r.metadata_json,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
