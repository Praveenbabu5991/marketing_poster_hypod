"""User details extracted from JWT token."""

from uuid import UUID

from pydantic import BaseModel


class UserDetails(BaseModel):
    """User details extracted from JWT token. Mirrors Hylancer user service."""

    user_id: UUID
    email: str
    name: str
    roles: list[str] = []
