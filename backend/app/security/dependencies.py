"""FastAPI auth dependencies: extract user from JWT."""

from typing import Optional

from fastapi import Header, HTTPException, status

from app.security.jwt_context import set_current_jwt
from app.security.models import UserDetails
from app.security.token_util import TokenUtil


async def get_current_user(
    authorization: Optional[str] = Header(None),
) -> Optional[UserDetails]:
    """Optional auth — returns None if no token."""
    if not authorization:
        return None
    try:
        token = authorization.removeprefix("Bearer ")
        # Stash the raw token so downstream interservice clients (e.g.
        # payment_client) can forward it the same way ai-service does.
        set_current_jwt(token)
        return TokenUtil.decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_authenticated_user(
    authorization: Optional[str] = Header(None),
) -> UserDetails:
    """Required auth — raises 401 if no token."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
