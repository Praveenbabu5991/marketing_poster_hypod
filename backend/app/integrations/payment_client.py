"""Payment-service client — pushes credit usage to the authoritative balance.

The marketing service keeps its own UserCredits / CreditTransaction tables
as a local mirror (useful for debugging, reconciliation, fast reads). The
payment-management-service is the source of truth: every successful local
deduction is followed by a POST to /api/v1/credits/internal/update so the
canonical balance stays in sync.

Authentication mirrors the ai-service pattern (ProjectServiceClient): the
caller's JWT is forwarded as `Authorization: Bearer <token>`. Payment-svc
trusts the API gateway to have already verified the JWT signature, exactly
like project-mgmt does for ai-service.

Endpoint contract (payment-management-service):
    POST {PAYMENT_SERVICE_URL}/api/v1/credits/internal/update
    Header: Authorization: Bearer <user-JWT>     (forwarded from inbound request)
    Body:   { "userId": "<uuid>", "creditUsed": <int>, "description": "<str?>" }
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional
from uuid import UUID

import httpx

from app.config import (
    PAYMENT_SERVICE_ENABLED,
    PAYMENT_SERVICE_INTERNAL_KEY,
    PAYMENT_SERVICE_TIMEOUT,
    PAYMENT_SERVICE_URL,
)
from app.security.jwt_context import get_current_jwt

logger = logging.getLogger(__name__)

_DEBIT_PATH = "/api/v1/credits/internal/update"
_REFUND_PATH = "/api/v1/credits/internal/refund"
_TOPUP_PATH = "/api/v1/credits/internal/top-up"

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (0.5, 1.0, 2.0)


def _enabled() -> bool:
    if not PAYMENT_SERVICE_ENABLED:
        return False
    if not PAYMENT_SERVICE_URL:
        logger.warning(
            "[PaymentClient] PAYMENT_SERVICE_ENABLED=true but PAYMENT_SERVICE_URL is missing; skipping call"
        )
        return False
    return True


def _headers(jwt: Optional[str]) -> Optional[dict]:
    """Build outbound headers. Returns None if no JWT is available
    (caller should skip the request — payment-svc will reject anyway).

    Sends BOTH headers because payment-svc demands both:
      * Authorization: Bearer <user-JWT>     -> Spring Security TokenFilter
      * X-Internal-Service-Key: <key>        -> CreditsController @RequestHeader
    """
    token = jwt or get_current_jwt()
    if not token:
        logger.warning(
            "[PaymentClient] No JWT available in current context; cannot call payment-svc"
        )
        return None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if PAYMENT_SERVICE_INTERNAL_KEY:
        headers["X-Internal-Service-Key"] = PAYMENT_SERVICE_INTERNAL_KEY
    return headers


async def _post_with_retry(
    path: str,
    payload: dict,
    jwt: Optional[str] = None,
) -> Optional[dict]:
    """POST to payment-svc with bounded retries on transient failures.

    Returns the parsed JSON body on 2xx, None on permanent failure.
    Never raises — credit drift is recoverable, agent failure isn't.
    """
    if not _enabled():
        return None

    headers = _headers(jwt)
    if headers is None:
        return None

    url = f"{PAYMENT_SERVICE_URL.rstrip('/')}{path}"
    last_err: Optional[str] = None

    for attempt in range(_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=PAYMENT_SERVICE_TIMEOUT) as client:
                resp = await client.post(url, json=payload, headers=headers)
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
            # 4xx is non-retryable: bad token, validation error, insufficient balance
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
    jwt: Optional[str] = None,
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
    return await _post_with_retry(_DEBIT_PATH, payload, jwt=jwt)


async def refund_usage(
    user_id: UUID,
    amount: int,
    description: Optional[str] = None,
    reference_id: Optional[str] = None,
    jwt: Optional[str] = None,
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
    return await _post_with_retry(_REFUND_PATH, payload, jwt=jwt)


def report_usage_sync(
    user_id: UUID,
    credit_used: int,
    description: Optional[str] = None,
    jwt: Optional[str] = None,
) -> Optional[dict]:
    """Sync variant for tool bodies that run outside an event loop.

    The JWT is read from the request-scoped ContextVar that
    `require_authenticated_user` set on the inbound FastAPI request.
    This works for sync tools as long as they run in the same context
    (LangGraph's tool executor preserves contextvars).
    """
    if credit_used <= 0:
        return None
    if not _enabled():
        return None

    headers = _headers(jwt)
    if headers is None:
        return None

    url = f"{PAYMENT_SERVICE_URL.rstrip('/')}{_DEBIT_PATH}"
    payload: dict = {"userId": str(user_id), "creditUsed": int(credit_used)}
    if description:
        payload["description"] = description

    last_err: Optional[str] = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            with httpx.Client(timeout=PAYMENT_SERVICE_TIMEOUT) as client:
                resp = client.post(url, json=payload, headers=headers)
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
            time.sleep(_BACKOFF_SECONDS[attempt])

    logger.error("[PaymentClient] (sync) failed after %d attempts: %s", _MAX_ATTEMPTS, last_err)
    return None


def refund_usage_sync(
    user_id: UUID,
    amount: int,
    description: Optional[str] = None,
    reference_id: Optional[str] = None,
    jwt: Optional[str] = None,
) -> Optional[dict]:
    """Sync refund for tool failure paths."""
    if amount <= 0:
        return None
    if not _enabled():
        return None

    headers = _headers(jwt)
    if headers is None:
        return None

    url = f"{PAYMENT_SERVICE_URL.rstrip('/')}{_REFUND_PATH}"
    payload: dict = {"userId": str(user_id), "amount": int(amount)}
    if description:
        payload["description"] = description
    if reference_id:
        payload["referenceId"] = reference_id

    last_err: Optional[str] = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            with httpx.Client(timeout=PAYMENT_SERVICE_TIMEOUT) as client:
                resp = client.post(url, json=payload, headers=headers)
            if 200 <= resp.status_code < 300:
                try:
                    return resp.json()
                except ValueError:
                    return {}
            if 400 <= resp.status_code < 500:
                logger.error(
                    "[PaymentClient] (sync refund) rejected status=%d body=%s",
                    resp.status_code, resp.text[:300],
                )
                return None
            last_err = f"HTTP {resp.status_code}"
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_err = f"{type(exc).__name__}: {exc}"

        if attempt < _MAX_ATTEMPTS - 1:
            time.sleep(_BACKOFF_SECONDS[attempt])

    logger.error("[PaymentClient] (sync refund) failed after %d attempts: %s", _MAX_ATTEMPTS, last_err)
    return None
