"""CSRF protection for endpoints authenticated by browser cookies."""

from __future__ import annotations

import re

from fastapi import HTTPException, Request

from config.settings import get_settings


def require_trusted_origin(request: Request) -> None:
    """Reject cookie-authenticated production requests from unknown origins."""
    settings = get_settings()
    origin = request.headers.get("origin")
    if not origin:
        if settings.is_production():
            raise HTTPException(status_code=403, detail="Origin header diperlukan")
        return

    is_exact_match = origin in settings.CORS_ALLOWED_ORIGINS
    is_regex_match = bool(
        settings.CORS_ALLOWED_ORIGIN_REGEX
        and re.fullmatch(settings.CORS_ALLOWED_ORIGIN_REGEX, origin)
    )
    if not (is_exact_match or is_regex_match):
        raise HTTPException(status_code=403, detail="Origin tidak diizinkan")
