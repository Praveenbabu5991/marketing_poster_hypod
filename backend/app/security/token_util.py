"""JWT token decode utility.

Decodes JWT without verification — API Gateway handles signature validation.
"""

import jwt
from uuid import UUID

from app.security.models import UserDetails


class TokenUtil:

    @staticmethod
    def decode_token(token: str) -> UserDetails:
        """Decode JWT token and extract user details (no signature verification)."""
        decoded = jwt.decode(token, options={"verify_signature": False})
        return TokenUtil._extract_user_details(decoded)

    @staticmethod
    def _extract_user_details(decoded: dict) -> UserDetails:
        user_id_str = decoded.get("sub")
        if not user_id_str:
            raise ValueError("Missing 'sub' claim in JWT token")

        email = decoded.get("email")
        if not email:
            raise ValueError("Missing 'email' claim in JWT token")

        name = decoded.get("name", "")
        roles = decoded.get("cognito:groups", [])
        if not isinstance(roles, list):
            roles = [roles] if roles else []

        return UserDetails(
            user_id=UUID(user_id_str),
            email=email,
            name=name,
            roles=roles,
        )
