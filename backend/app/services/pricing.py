"""Pricing — single source of truth for user-facing credit costs.

Internal API cost (USD) is computed in app.config.calculate_cost using VERTEX_PRICING.
This module converts actions into INR credits (1 credit = ₹1) with margin built in.

Matches the user's pricing plan:
    Text  ≈ ₹2 cost  → sell 3 credits  (~50% margin)
    Image ≈ ₹7 cost  → sell 10 credits (~43% margin)
    Video 8s  ≈ ₹280 → sell 400 credits
    Video 16s ≈ ₹560 → sell 800 credits
"""

from math import ceil
from typing import Optional

from app.config import CREDIT_USD_TO_INR, calculate_cost


# Flat credit costs per user-facing action — kept explicit so pricing is easy to explain.
ACTION_CREDITS = {
    "llm_text": 3,       # per LLM call (orchestrator or sub-agent)
    "image": 10,         # per image generation
    "video_8s": 400,     # 8-second video
    "video_16s": 800,    # 16-second video
    "search": 1,         # web search / trending
}


def credits_for_action(action: str) -> int:
    """Return flat credit cost for a user-facing action."""
    return ACTION_CREDITS.get(action, 0)


def credits_for_video(duration_seconds: int) -> int:
    """Credit cost for a video by duration. Rounds up to the next 8s block."""
    if duration_seconds <= 0:
        return ACTION_CREDITS["video_8s"]
    blocks = ceil(duration_seconds / 8)
    return blocks * ACTION_CREDITS["video_8s"]


def estimate_credits(
    event_type: str,
    *,
    duration_sec: Optional[int] = None,
) -> int:
    """Upfront credit estimate for UI pre-check gates.

    Args:
        event_type: "llm_text" | "image" | "video" | "search"
        duration_sec: video length (required for event_type="video")
    """
    if event_type == "video":
        return credits_for_video(duration_sec or 8)
    return credits_for_action(event_type)


def usd_cost_to_inr(cost_usd: float) -> float:
    """Convert internal USD API cost to INR (for admin dashboards)."""
    return round(cost_usd * CREDIT_USD_TO_INR, 2)


def actual_cost_inr(
    model_name: str,
    action_type: str,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    unit_count: int = 1,
    video_duration_seconds: int = 0,
) -> float:
    """Compute actual API cost in INR (for margin calculations)."""
    usd = calculate_cost(
        model_name=model_name,
        action_type=action_type,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        unit_count=unit_count,
        video_duration_seconds=video_duration_seconds,
    )
    return usd_cost_to_inr(usd)
