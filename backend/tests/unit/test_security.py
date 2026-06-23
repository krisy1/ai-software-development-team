from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from jose import jwt

from app.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_api_key,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_password_returns_string(self):
        result = hash_password("my_secure_password")
        assert isinstance(result, str)
        assert len(result) > 10

    def test_verify_password_correct(self):
        hashed = hash_password("correct_password")
        assert verify_password("correct_password", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_same_password_different_hashes(self):
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2


class TestJWTTokens:
    def test_create_access_token_returns_string(self):
        token = create_access_token(subject="user123")
        assert isinstance(token, str)

    def test_decode_valid_token(self):
        token = create_access_token(subject="user456")
        payload = decode_access_token(token)
        assert payload["sub"] == "user456"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_token_with_custom_expiry(self):
        token = create_access_token(subject="user789", expires_delta=timedelta(hours=1))
        payload = decode_access_token(token)
        assert payload["sub"] == "user789"

    def test_decode_invalid_token_raises_error(self):
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token("not.a.real.jwt")

    def test_decode_token_wrong_type_raises_error(self):
        payload = {
            "sub": "user",
            "exp": 9999999999,
            "iat": 1000000000,
            "type": "refresh",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token(token)

    def test_token_contains_expected_claims(self):
        token = create_access_token(subject="test_user")
        payload = decode_access_token(token)
        assert "sub" in payload
        assert "exp" in payload
        assert "iat" in payload
        assert "type" in payload


class TestApiKeyVerification:
    def test_verify_correct_api_key(self):
        with patch.object(settings, "API_KEY", "test-api-key-123"):
            assert verify_api_key("test-api-key-123") is True

    def test_verify_wrong_api_key(self):
        with patch.object(settings, "API_KEY", "test-api-key-123"):
            assert verify_api_key("wrong-key") is False

    def test_verify_empty_api_key_returns_false(self):
        with patch.object(settings, "API_KEY", ""):
            assert verify_api_key("anything") is False
