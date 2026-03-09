"""Tests for JWT auth."""

import uuid

import jwt
import pytest

from app.security.models import UserDetails
from app.security.token_util import TokenUtil


class TestTokenUtil:

    def test_decode_valid_token(self):
        user_id = str(uuid.uuid4())
        payload = {
            "sub": user_id,
            "email": "user@test.com",
            "name": "Test User",
            "cognito:groups": ["Admin"],
        }
        token = jwt.encode(payload, "secret", algorithm="HS256")
        user = TokenUtil.decode_token(token)

        assert str(user.user_id) == user_id
        assert user.email == "user@test.com"
        assert user.name == "Test User"
        assert user.roles == ["Admin"]

    def test_decode_missing_sub(self):
        payload = {"email": "user@test.com"}
        token = jwt.encode(payload, "secret", algorithm="HS256")
        with pytest.raises(ValueError, match="sub"):
            TokenUtil.decode_token(token)

    def test_decode_missing_email(self):
        payload = {"sub": str(uuid.uuid4())}
        token = jwt.encode(payload, "secret", algorithm="HS256")
        with pytest.raises(ValueError, match="email"):
            TokenUtil.decode_token(token)

    def test_decode_no_roles(self):
        payload = {
            "sub": str(uuid.uuid4()),
            "email": "user@test.com",
        }
        token = jwt.encode(payload, "secret", algorithm="HS256")
        user = TokenUtil.decode_token(token)
        assert user.roles == []

    def test_decode_string_role(self):
        payload = {
            "sub": str(uuid.uuid4()),
            "email": "user@test.com",
            "cognito:groups": "SingleRole",
        }
        token = jwt.encode(payload, "secret", algorithm="HS256")
        user = TokenUtil.decode_token(token)
        assert user.roles == ["SingleRole"]

    def test_decode_invalid_token(self):
        with pytest.raises(Exception):
            TokenUtil.decode_token("not-a-jwt")


class TestUserDetails:

    def test_model_creation(self):
        user = UserDetails(
            user_id=uuid.uuid4(),
            email="test@test.com",
            name="Test",
            roles=["Hylancer"],
        )
        assert user.email == "test@test.com"
        assert "Hylancer" in user.roles
