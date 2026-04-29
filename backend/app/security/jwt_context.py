"""Per-request JWT context.

The marketing service receives the user's JWT on the inbound request and
needs to forward it to downstream services (e.g. payment-svc) — same
pattern as ai-service's ProjectServiceClient. Because the deduction
points (LangGraph callbacks, sync tool bodies) live many layers below
the FastAPI dependency, we stash the raw token in a ContextVar so any
code in the same async/threaded context can read it back.

Set on the inbound auth dependency. Read by app/integrations/payment_client.
"""

from contextvars import ContextVar
from typing import Optional

# The raw bearer token (without the "Bearer " prefix), or None for
# unauthenticated requests / background work.
current_jwt: ContextVar[Optional[str]] = ContextVar("current_jwt", default=None)


def set_current_jwt(token: Optional[str]) -> None:
    """Store the raw JWT for the current request scope."""
    current_jwt.set(token)


def get_current_jwt() -> Optional[str]:
    """Return the JWT for the current request scope, or None if not set."""
    return current_jwt.get()
