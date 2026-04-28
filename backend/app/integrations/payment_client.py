"""Payment-service client — pushes credit usage to the authoritative balance.

The marketing service keeps its own UserCredits / CreditTransaction tables as a
local mirror (useful for debugging, reconciliation, fast reads). The
payment-management-service is the source of truth: every successful local
deduction is followed by a POST to /api/v1/credits/internal/update so the
canonical balance stays in sync.

Endpoint contract (payment-management-service):
    POST {PAYMENT_SERVICE_URL}/api/v1/credits/internal/update
    Header: X-Internal-Service-Key: <PAYMENT_SERVICE_INTERNAL_KEY>
    Body:   { "userId": "<uuid>", "creditUsed": <int>, "description": "<str?>" }
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional
from uuid import UUID

import httpx

from app.config import (
    PAYMENT_SERVICE_ENABLED,
    PAYMENT_SERVICE_INTERNAL_KEY,
    PAYMENT_SERVICE_TIMEOUT,
    PAYMENT_SERVICE_URL,
)

logger = logging.getLogger(__name__)

_DEBIT_PATH = "/api/v1/credits/internal/update"
_REFUND_PATH = "/api/v1/credits/internal/refund"
_TOPUP_PATH = "/api/v1/credits/internal/top-up"

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (0.5, 1.0, 2.0)


def _enabled() -> bool:
    if not PAYMENT_SERVICE_ENABLED:
        return False
    if not PAYMENT_SERVICE_URL or not PAYMENT_SERVICE_INTERNAL_KEY:
        logger.warning(
            "[PaymentClient] PAYMENT_SERVICE_ENABLED=true but URL or KEY is missing; skipping call"
        )
        return False
    return True


def _headers() -> dict:
    return {
        "X-Internal-Service-Key": PAYMENT_SERVICE_INTERNAL_KEY,
        "Content-Type": "application/json",
    }


async def _post_with_retry(path: str, payload: dict) -> Optional[dict]:
    """POST to payment-svc with bounded retries on transient failures.

    Returns the parsed JSON body on 2xx, None on permanent failure.
    Never raises — credit drift is recoverable, agent failure isn't.
    """
    if not _enabled():
        return None

    url = f"{PAYMENT_SERVICE_URL.rstrip('/')}{path}"
    last_err: Optional[str] = None

    for attempt in range(_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=PAYMENT_SERVICE_TIMEOUT) as client:
                resp = await client.post(url, json=payload, headers=_headers())
            if 200 <= resp.status_code < 300:
                logger.info(
                    "[PaymentClient] %s userId=%s creditUsed=%s status=%d",
                    path,
                    payload.get("userId"),
                    payload.get("creditUsed") or payload.get("amount"),
                    resp.status_code,
                )
                try:
                    return resp.json()
                except ValueError:
                    return {}
            # 4xx is non-retryable: bad key, validation error, insufficient balance
            if 400 <= resp.status_code < 500:
                logger.error(
                    "[PaymentClient] %s rejected (status=%d body=%s) — not retrying",
                    path,
                    resp.status_code,
                    resp.text[:300],
                )
                return None
            last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_err = f"{type(exc).__name__}: {exc}"

        if attempt < _MAX_ATTEMPTS - 1:
            await asyncio.sleep(_BACKOFF_SECONDS[attempt])

    logger.error(
        "[PaymentClient] %s failed after %d attempts: %s",
        path,
        _MAX_ATTEMPTS,
        last_err,
    )
    return None


async def report_usage(
    user_id: UUID,
    credit_used: int,
    description: Optional[str] = None,
) -> Optional[dict]:
    """Tell payment-svc to deduct `credit_used` from the user's balance.

    Mirrors the contract management agreed on: marketing sends only
    {userId, creditUsed} per LLM/tool call; payment-svc handles the math.
    """
    if credit_used <= 0:
        return None
    payload = {
        "userId": str(user_id),
        "creditUsed": int(credit_used),
    }
    if description:
        payload["description"] = description
    return await _post_with_retry(_DEBIT_PATH, payload)


async def refund_usage(
    user_id: UUID,
    amount: int,
    description: Optional[str] = None,
    reference_id: Optional[str] = None,
) -> Optional[dict]:
    """Refund `amount` credits when a pre-deducted call fails (image/video)."""
    if amount <= 0:
        return None
    payload = {
        "userId": str(user_id),
        "amount": int(amount),
    }
    if description:
        payload["description"] = description
    if reference_id:
        payload["referenceId"] = reference_id
    return await _post_with_retry(_REFUND_PATH, payload)


def report_usage_sync(
    user_id: UUID,
    credit_used: int,
    description: Optional[str] = None,
) -> Optional[dict]:
    """Sync variant for tool bodies that run outside an event loop."""
    if credit_used <= 0:
        return None
    if not _enabled():
        return None

    url = f"{PAYMENT_SERVICE_URL.rstrip('/')}{_DEBIT_PATH}"
    payload: dict = {"userId": str(user_id), "creditUsed": int(credit_used)}
    if description:
        payload["description"] = description

    last_err: Optional[str] = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            with httpx.Client(timeout=PAYMENT_SERVICE_TIMEOUT) as client:
                resp = client.post(url, json=payload, headers=_headers())
            if 200 <= resp.status_code < 300:
                logger.info(
                    "[PaymentClient] (sync) %s userId=%s creditUsed=%s",
                    _DEBIT_PATH, payload["userId"], payload["creditUsed"],
                )
                try:
                    return resp.json()
                except ValueError:
                    return {}
            if 400 <= resp.status_code < 500:
                logger.error(
                    "[PaymentClient] (sync) %s rejected status=%d body=%s",
                    _DEBIT_PATH, resp.status_code, resp.text[:300],
                )
                return None
            last_err = f"HTTP {resp.status_code}"
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_err = f"{type(exc).__name__}: {exc}"

        if attempt < _MAX_ATTEMPTS - 1:
            import time
            time.sleep(_BACKOFF_SECONDS[attempt])

    logger.error("[PaymentClient] (sync) failed after %d attempts: %s", _MAX_ATTEMPTS, last_err)
    return None
