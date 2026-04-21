"""Credit wallet service — atomic deduct / refund / top-up with audit logging.

All writes take a `SELECT … FOR UPDATE` lock on the user_credits row to prevent
race conditions when concurrent requests hit the same user.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DEFAULT_FREE_CREDITS
from app.database import async_session_factory
from app.models.credit import CreditTransaction, UserCredits


class InsufficientCreditsError(Exception):
    """Raised when a deduction would take balance below zero."""

    def __init__(self, balance: int, required: int):
        self.balance = balance
        self.required = required
        super().__init__(
            f"Insufficient credits: balance={balance}, required={required}"
        )


async def _get_or_create_wallet(db: AsyncSession, user_id: UUID) -> UserCredits:
    """Return the user's wallet, creating a default free-tier wallet if missing.

    The wallet is fetched with a row-level lock to prevent concurrent mutation.
    """
    stmt = select(UserCredits).where(UserCredits.user_id == user_id).with_for_update()
    result = await db.execute(stmt)
    wallet = result.scalar_one_or_none()
    if wallet is not None:
        return wallet

    # Create default wallet for first-time users (free tier + signup bonus)
    wallet = UserCredits(
        user_id=user_id,
        plan="free",
        balance=DEFAULT_FREE_CREDITS,
        monthly_allowance=DEFAULT_FREE_CREDITS,
        resets_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(wallet)
    await db.flush()

    if DEFAULT_FREE_CREDITS > 0:
        db.add(
            CreditTransaction(
                user_id=user_id,
                delta=DEFAULT_FREE_CREDITS,
                balance_after=DEFAULT_FREE_CREDITS,
                reason="signup_bonus",
                metadata_json={"plan": "free"},
            )
        )
        await db.flush()
    return wallet


async def get_balance(db: AsyncSession, user_id: UUID) -> UserCredits:
    """Return the user's wallet (creating it on first call)."""
    return await _get_or_create_wallet(db, user_id)


async def check_and_deduct(
    db: AsyncSession,
    user_id: UUID,
    credits: int,
    reason: str,
    *,
    usage_log_id: Optional[UUID] = None,
    metadata: Optional[dict] = None,
) -> int:
    """Atomically check balance and deduct `credits`. Returns balance_after.

    Raises InsufficientCreditsError if balance would go below zero.
    Use BEFORE expensive API calls (image, video). Logs a CreditTransaction.
    """
    if credits <= 0:
        wallet = await _get_or_create_wallet(db, user_id)
        return wallet.balance

    wallet = await _get_or_create_wallet(db, user_id)
    if wallet.balance < credits:
        raise InsufficientCreditsError(wallet.balance, credits)

    wallet.balance -= credits
    db.add(
        CreditTransaction(
            user_id=user_id,
            delta=-credits,
            balance_after=wallet.balance,
            reason=reason,
            usage_log_id=usage_log_id,
            metadata_json=metadata or {},
        )
    )
    await db.commit()
    return wallet.balance


async def post_deduct(
    db: AsyncSession,
    user_id: UUID,
    credits: int,
    reason: str,
    *,
    usage_log_id: Optional[UUID] = None,
    metadata: Optional[dict] = None,
) -> tuple[int, bool]:
    """Deduct AFTER a call has succeeded (used for LLM where token count is only
    known post-call). Allows balance to go negative (overdraft) — we can't stop
    mid-generation, so we log it and let admin reconcile.

    Returns (balance_after, overdraft_flag).
    """
    if credits <= 0:
        wallet = await _get_or_create_wallet(db, user_id)
        return wallet.balance, False

    wallet = await _get_or_create_wallet(db, user_id)
    overdraft = wallet.balance < credits
    wallet.balance -= credits
    meta = dict(metadata or {})
    if overdraft:
        meta["overdraft"] = True
    db.add(
        CreditTransaction(
            user_id=user_id,
            delta=-credits,
            balance_after=wallet.balance,
            reason=reason,
            usage_log_id=usage_log_id,
            metadata_json=meta,
        )
    )
    await db.commit()
    return wallet.balance, overdraft


async def refund(
    db: AsyncSession,
    user_id: UUID,
    credits: int,
    reason: str,
    *,
    usage_log_id: Optional[UUID] = None,
    metadata: Optional[dict] = None,
) -> int:
    """Refund `credits` back to the user's wallet. Returns balance_after.

    Called when a pre-deducted API call fails.
    """
    if credits <= 0:
        wallet = await _get_or_create_wallet(db, user_id)
        return wallet.balance

    wallet = await _get_or_create_wallet(db, user_id)
    wallet.balance += credits
    db.add(
        CreditTransaction(
            user_id=user_id,
            delta=credits,
            balance_after=wallet.balance,
            reason=reason,
            usage_log_id=usage_log_id,
            metadata_json=metadata or {},
        )
    )
    await db.commit()
    return wallet.balance


async def top_up(
    db: AsyncSession,
    user_id: UUID,
    credits: int,
    reason: str = "stripe_topup",
    *,
    metadata: Optional[dict] = None,
) -> int:
    """Add `credits` to the wallet (e.g. after Stripe payment). Returns balance_after."""
    if credits <= 0:
        wallet = await _get_or_create_wallet(db, user_id)
        return wallet.balance

    wallet = await _get_or_create_wallet(db, user_id)
    wallet.balance += credits
    db.add(
        CreditTransaction(
            user_id=user_id,
            delta=credits,
            balance_after=wallet.balance,
            reason=reason,
            metadata_json=metadata or {},
        )
    )
    await db.commit()
    return wallet.balance


async def set_plan(
    db: AsyncSession,
    user_id: UUID,
    plan: str,
    monthly_allowance: int,
    *,
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    top_up_credits: bool = True,
) -> UserCredits:
    """Switch the user to a new plan. Optionally top up by `monthly_allowance`.

    Called from the Stripe webhook when a subscription is created/renewed.
    """
    wallet = await _get_or_create_wallet(db, user_id)
    wallet.plan = plan
    wallet.monthly_allowance = monthly_allowance
    wallet.resets_at = datetime.now(timezone.utc) + timedelta(days=30)
    if stripe_customer_id:
        wallet.stripe_customer_id = stripe_customer_id
    if stripe_subscription_id:
        wallet.stripe_subscription_id = stripe_subscription_id

    if top_up_credits and monthly_allowance > 0:
        wallet.balance += monthly_allowance
        db.add(
            CreditTransaction(
                user_id=user_id,
                delta=monthly_allowance,
                balance_after=wallet.balance,
                reason="plan_reset",
                metadata_json={"plan": plan},
            )
        )
    await db.commit()
    return wallet


# --- Helpers that open their own session (for callbacks / tools) ---

async def check_and_deduct_standalone(
    user_id: UUID,
    credits: int,
    reason: str,
    *,
    metadata: Optional[dict] = None,
) -> int:
    """Same as check_and_deduct but opens its own session. Used by tools."""
    async with async_session_factory() as db:
        return await check_and_deduct(
            db, user_id, credits, reason, metadata=metadata
        )


async def refund_standalone(
    user_id: UUID,
    credits: int,
    reason: str,
    *,
    metadata: Optional[dict] = None,
) -> int:
    async with async_session_factory() as db:
        return await refund(db, user_id, credits, reason, metadata=metadata)


async def post_deduct_standalone(
    user_id: UUID,
    credits: int,
    reason: str,
    *,
    usage_log_id: Optional[UUID] = None,
    metadata: Optional[dict] = None,
) -> tuple[int, bool]:
    async with async_session_factory() as db:
        return await post_deduct(
            db, user_id, credits, reason,
            usage_log_id=usage_log_id, metadata=metadata,
        )
