"""Subscription plan catalog — user-supplied INR pricing + credit amounts.

Kept as a plain dict so the frontend can list plans without DB queries.
`stripe_price_id` is populated from env when real Stripe integration ships.
"""

import os


PLANS: dict[str, dict] = {
    "free": {
        "name": "Free",
        "price_inr": 0,
        "credits": 50,
        "description": "Try the platform — 50 credits free on signup.",
        "stripe_price_id": None,
        "features": [
            "50 credits (signup bonus)",
            "Text + image generation",
            "No video access",
        ],
    },
    "starter": {
        "name": "Starter",
        "price_inr": 299,
        "credits": 300,
        "description": "For hobbyists — covers ~30 images or 1 short video/month.",
        "stripe_price_id": os.getenv("STRIPE_PRICE_STARTER"),
        "features": [
            "300 credits/month",
            "Text + image + short video",
            "Single brand workspace",
        ],
    },
    "growth": {
        "name": "Growth",
        "price_inr": 799,
        "credits": 850,
        "description": "For small creators — ~2 videos + images/month.",
        "stripe_price_id": os.getenv("STRIPE_PRICE_GROWTH"),
        "features": [
            "850 credits/month",
            "All content types",
            "Up to 3 brand workspaces",
        ],
    },
    "pro": {
        "name": "Pro",
        "price_inr": 1499,
        "credits": 1800,
        "description": "For solo creators/freelancers — ~4 videos/month.",
        "stripe_price_id": os.getenv("STRIPE_PRICE_PRO"),
        "features": [
            "1,800 credits/month",
            "All content types + 16s videos",
            "Up to 10 brand workspaces",
        ],
    },
    "scale": {
        "name": "Scale",
        "price_inr": 2999,
        "credits": 4000,
        "description": "For agencies — ~10 videos + posts/month.",
        "stripe_price_id": os.getenv("STRIPE_PRICE_SCALE"),
        "features": [
            "4,000 credits/month",
            "All content types + priority queue",
            "Unlimited brand workspaces",
        ],
    },
}


def get_plan(plan_id: str) -> dict | None:
    return PLANS.get(plan_id)


def plan_by_stripe_price_id(price_id: str) -> tuple[str, dict] | None:
    """Look up plan + metadata by Stripe price_id — used by webhook handler."""
    for pid, meta in PLANS.items():
        if meta.get("stripe_price_id") == price_id:
            return pid, meta
    return None
