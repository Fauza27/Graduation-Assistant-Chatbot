from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import jwt
import pytest
from fastapi import HTTPException, Response

from config.settings import Settings
from src.auth import jwt_utils
from src.auth.refresh_tokens import (
    InvalidRefreshTokenError,
    RefreshTokenService,
    set_refresh_cookie,
)


def test_access_token_has_identity_and_lifecycle_claims(monkeypatch):
    monkeypatch.setattr(jwt_utils.settings, "JWT_EXPIRATION_MINUTES", 30)
    monkeypatch.setattr(jwt_utils.settings, "JWT_SECRET_KEY", "x" * 32)
    token = jwt_utils.create_access_token({"sub": "mhs-1", "role": "mahasiswa"})
    payload = jwt_utils.verify_access_token(token)

    assert payload["type"] == "access"
    assert payload["jti"]
    assert payload["iat"] < payload["exp"]


def test_token_without_access_type_is_rejected(monkeypatch):
    monkeypatch.setattr(jwt_utils.settings, "JWT_SECRET_KEY", "x" * 32)
    token = jwt.encode(
        {
            "sub": "mhs-1",
            "role": "mahasiswa",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        jwt_utils.settings.JWT_SECRET_KEY,
        algorithm=jwt_utils.settings.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc_info:
        jwt_utils.verify_access_token(token)
    assert exc_info.value.status_code == 401


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValueError, match="JWT_SECRET_KEY production"):
        Settings(
            open_api_key="test-key",
            supabase_url="https://example.supabase.co",
            supabase_service_key="test-service-key",
            TELEGRAM_BOT_TOKEN="test-bot-token",
            ENVIRONMENT="production",
            TELEGRAM_WEBHOOK_URL="",
            TELEGRAM_WEBHOOK_SECRET="",
            JWT_SECRET_KEY="super-secret-key-change-in-production",
            JWT_EXPIRATION_MINUTES=30,
            ENABLE_REFRESH_TOKENS=True,
        )


def test_refresh_token_reuse_revokes_entire_family(monkeypatch):
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(
        data=[
            {
                "subject_id": "mhs-1",
                "role": "mahasiswa",
                "family_id": "family-1",
                "token_payload": {},
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(days=1)
                ).isoformat(),
                "revoked_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
    )
    revoke_rpc = Mock()
    revoke_rpc.execute.return_value = SimpleNamespace(data=1)
    client = Mock()
    client.table.return_value = query
    client.rpc.return_value = revoke_rpc

    service = RefreshTokenService(client)
    with pytest.raises(InvalidRefreshTokenError, match="sudah digunakan"):
        service.rotate("reused-token")

    client.rpc.assert_called_once_with(
        "revoke_refresh_token_family",
        {"p_family_id": "family-1"},
    )


def test_session_refresh_cookie_has_no_max_age():
    response = Response()

    set_refresh_cookie(response, "token", role="admin", persistent=False)

    cookie = response.headers["set-cookie"]
    assert "Max-Age" not in cookie
    assert "HttpOnly" in cookie


def test_persistent_refresh_cookie_has_max_age():
    response = Response()

    set_refresh_cookie(response, "token", role="admin", persistent=True)

    assert "Max-Age" in response.headers["set-cookie"]
