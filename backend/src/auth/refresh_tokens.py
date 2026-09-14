"""Opaque refresh-token issuance, rotation, revocation, and cookies."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Response
from loguru import logger
from supabase import Client

from config.settings import get_settings


class InvalidRefreshTokenError(ValueError):
    """Raised when a refresh token is missing, expired, or already consumed."""


@dataclass(frozen=True)
class RotatedRefreshToken:
    token: str
    payload: dict[str, Any]


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(48)


class RefreshTokenService:
    """Persist only token hashes; rotate tokens atomically through a DB RPC."""

    def __init__(self, supabase: Client):
        self._supabase = supabase
        self._settings = get_settings()

    def issue(self, payload: dict[str, Any]) -> str:
        token = _new_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self._settings.REFRESH_TOKEN_EXPIRATION_DAYS
        )
        self._supabase.table("auth_refresh_tokens").insert(
            {
                "token_hash": _hash_token(token),
                "subject_id": str(payload["sub"]),
                "role": str(payload["role"]),
                "family_id": str(uuid.uuid4()),
                "token_payload": payload,
                "expires_at": expires_at.isoformat(),
            }
        ).execute()
        return token

    def rotate(self, token: str) -> RotatedRefreshToken:
        current_hash = _hash_token(token)
        result = (
            self._supabase.table("auth_refresh_tokens")
            .select("subject_id,role,family_id,token_payload,expires_at,revoked_at")
            .eq("token_hash", current_hash)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise InvalidRefreshTokenError("Refresh token tidak valid")

        row = result.data[0]
        expires_at = datetime.fromisoformat(
            str(row["expires_at"]).replace("Z", "+00:00")
        )
        if row.get("revoked_at"):
            self._supabase.rpc(
                "revoke_refresh_token_family",
                {"p_family_id": row["family_id"]},
            ).execute()
            raise InvalidRefreshTokenError("Refresh token sudah digunakan")
        if expires_at <= datetime.now(timezone.utc):
            raise InvalidRefreshTokenError(
                "Refresh token kedaluwarsa atau sudah digunakan"
            )

        payload = dict(row.get("token_payload") or {})
        payload["sub"] = str(row["subject_id"])
        payload["role"] = str(row["role"])

        replacement = _new_token()
        replacement_hash = _hash_token(replacement)
        replacement_expiry = datetime.now(timezone.utc) + timedelta(
            days=self._settings.REFRESH_TOKEN_EXPIRATION_DAYS
        )
        rotated = self._supabase.rpc(
            "rotate_refresh_token",
            {
                "p_current_hash": current_hash,
                "p_new_hash": replacement_hash,
                "p_subject_id": payload["sub"],
                "p_role": payload["role"],
                "p_family_id": row["family_id"],
                "p_token_payload": payload,
                "p_expires_at": replacement_expiry.isoformat(),
            },
        ).execute()
        if not rotated.data:
            raise InvalidRefreshTokenError("Refresh token sudah digunakan")

        return RotatedRefreshToken(token=replacement, payload=payload)

    def revoke(self, token: str) -> None:
        try:
            self._supabase.rpc(
                "revoke_refresh_token",
                {"p_token_hash": _hash_token(token)},
            ).execute()
        except Exception as exc:
            # Logout tetap menghapus cookie di client. Kegagalan server dicatat
            # agar operator dapat menindaklanjuti tanpa membocorkan token.
            logger.warning("Gagal mencabut refresh token: {}", type(exc).__name__)


def refresh_cookie_name(role: str = "mahasiswa") -> str:
    settings = get_settings()
    return (
        settings.ADMIN_REFRESH_COOKIE_NAME
        if role == "admin"
        else settings.REFRESH_COOKIE_NAME
    )


def set_refresh_cookie(
    response: Response,
    token: str,
    role: str = "mahasiswa",
    *,
    persistent: bool = True,
) -> None:
    settings = get_settings()
    max_age = (
        settings.REFRESH_TOKEN_EXPIRATION_DAYS * 24 * 60 * 60
        if persistent
        else None
    )
    response.set_cookie(
        key=refresh_cookie_name(role),
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.is_production(),
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        path="/api",
    )


def clear_refresh_cookie(response: Response, role: str = "mahasiswa") -> None:
    settings = get_settings()
    response.delete_cookie(
        key=refresh_cookie_name(role),
        httponly=True,
        secure=settings.is_production(),
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        path="/api",
    )
