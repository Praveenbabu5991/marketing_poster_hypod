"""Admin access control.

Admin access is granted if the authenticated user has EITHER:
  - 'ADMIN' in their Cognito groups (UserDetails.roles), OR
  - Their user_id is in the ADMIN_USER_IDS env allow-list.
"""

from fastapi import Depends, HTTPException, status

from app.config import ADMIN_USER_IDS
from app.security.dependencies import require_authenticated_user
from app.security.models import UserDetails


def is_admin(user: UserDetails) -> bool:
    if "ADMIN" in (user.roles or []):
        return True
    return str(user.user_id) in ADMIN_USER_IDS


async def require_admin(
    user: UserDetails = Depends(require_authenticated_user),
) -> UserDetails:
    if not is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
