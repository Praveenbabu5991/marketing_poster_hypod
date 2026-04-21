"""Billing endpoints — plan catalog + Stripe-ready stubs.

Phase 3 ships scaffolding only: plan listing, checkout URL placeholder,
webhook endpoint that logs + returns 200, and an admin-topup endpoint that
lets operators credit users manually during beta (before Stripe is wired).

The actual Stripe SDK calls will be added in Phase 5 — this file already has
the exact shape those calls will replace (marked `# TODO: stripe`).
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.security.admin import require_admin
from app.security.dependencies import require_authenticated_user
from app.security.models import UserDetails
from app.services import credit_service
from app.services.plans import PLANS, get_plan
from app.schemas.credit import TopUpRequest

logger = logging.getLogger(__name__)
router = APIRouter()


class PlanOut(BaseModel):
    id: str
    name: str
    price_inr: int
    credits: int
    description: str
    features: list[str]
    stripe_price_id: Optional[str] = None


@router.get("/plans", response_model=list[PlanOut])
async def list_plans():
    """Public catalog of subscription plans."""
    return [
        PlanOut(
            id=pid,
            name=p["name"],
            price_inr=p["price_inr"],
            credits=p["credits"],
            description=p["description"],
            features=p["features"],
            stripe_price_id=p.get("stripe_price_id"),
        )
        for pid, p in PLANS.items()
    ]


class CheckoutRequest(BaseModel):
    plan_id: str
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: Optional[str]
    message: str


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    user: UserDetails = Depends(require_authenticated_user),
):
    """Create a Stripe Checkout Session for `plan_id`.

    SCAFFOLDING: returns a placeholder response until Stripe keys are configured.
    Once STRIPE_API_KEY is set, replace the TODO block with a real SDK call.
    """
    plan = get_plan(body.plan_id)
    if not plan:
        raise HTTPException(400, f"Unknown plan: {body.plan_id}")
    if not plan.get("stripe_price_id"):
        return CheckoutResponse(
            checkout_url=None,
            message=(
                f"Plan '{body.plan_id}' is not yet available for purchase. "
                "Contact support for manual provisioning."
            ),
        )

    # TODO: stripe — replace with:
    #   import stripe
    #   stripe.api_key = STRIPE_API_KEY
    #   session = stripe.checkout.Session.create(
    #       mode="subscription",
    #       line_items=[{"price": plan["stripe_price_id"], "quantity": 1}],
    #       success_url=body.success_url, cancel_url=body.cancel_url,
    #       client_reference_id=str(user.user_id),
    #       customer_email=user.email,
    #   )
    #   return CheckoutResponse(checkout_url=session.url, message="ok")
    return CheckoutResponse(
        checkout_url=None,
        message="Stripe integration not yet enabled — contact support.",
    )


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Stripe webhook handler.

    SCAFFOLDING: logs the payload and returns 200 so Stripe doesn't retry.
    When real integration ships, this needs to:
      1. Verify the Stripe-Signature header (stripe.Webhook.construct_event)
      2. Handle events: checkout.session.completed, invoice.paid, subscription.*
      3. Call credit_service.set_plan() + top_up() to credit the user
    """
    body = await request.body()
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    event_type = payload.get("type", "<no-type>")
    logger.info("[STRIPE] Received webhook type=%s bytes=%d", event_type, len(body))

    # TODO: stripe — verify signature + dispatch events.
    # Example for checkout.session.completed:
    #   user_id = payload["data"]["object"]["client_reference_id"]
    #   price_id = payload["data"]["object"]["line_items"]["data"][0]["price"]["id"]
    #   plan_meta = plan_by_stripe_price_id(price_id)
    #   if plan_meta:
    #       plan_id, plan = plan_meta
    #       await credit_service.set_plan(db, UUID(user_id), plan_id,
    #                                      plan["credits"], top_up_credits=True)

    return {"received": True, "handled": False}


@router.post("/admin-topup")
async def admin_topup(
    body: TopUpRequest,
    admin: UserDetails = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: manually credit a user's wallet (beta / support escalations)."""
    if body.credits <= 0:
        raise HTTPException(400, "credits must be positive")
    balance = await credit_service.top_up(
        db,
        body.user_id,
        body.credits,
        reason=body.reason or "admin_topup",
        metadata={"admin_id": str(admin.user_id), "note": body.note or ""},
    )
    return {"user_id": str(body.user_id), "balance": balance, "credited": body.credits}


class SetPlanRequest(BaseModel):
    user_id: UUID
    plan_id: str
    top_up_credits: bool = True


@router.post("/admin-set-plan")
async def admin_set_plan(
    body: SetPlanRequest,
    admin: UserDetails = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: switch a user's plan (and optionally grant the monthly allowance)."""
    plan = get_plan(body.plan_id)
    if not plan:
        raise HTTPException(400, f"Unknown plan: {body.plan_id}")
    wallet = await credit_service.set_plan(
        db,
        body.user_id,
        body.plan_id,
        plan["credits"],
        top_up_credits=body.top_up_credits,
    )
    return {
        "user_id": str(wallet.user_id),
        "plan": wallet.plan,
        "balance": wallet.balance,
        "monthly_allowance": wallet.monthly_allowance,
    }
