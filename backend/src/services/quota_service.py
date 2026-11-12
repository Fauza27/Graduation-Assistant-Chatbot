"""
Shared quota management service for daily rate limiting.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo
from loguru import logger
from supabase import Client, create_client

from config.settings import get_settings
from src.monitoring.errors import SupabaseServiceError


@lru_cache(maxsize=1)
def _get_supabase_client() -> Client:
    """Reuse single Supabase client instance across requests."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


def _get_current_date() -> str:
    """Mengembalikan tanggal hari ini sesuai zona waktu aplikasi (WITA / Asia/Makassar)."""
    settings = get_settings()
    tz_name = getattr(settings, "TIMEZONE", "Asia/Makassar")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Asia/Makassar")
    return datetime.now(tz).strftime("%Y-%m-%d")


def check_and_update_quota(
    user_id: str,
    daily_limit: int | None = None,
    *,
    allow_on_failure: bool = True,
) -> bool:
    """
    Atomically increment quota and check daily limit via RPC.

    Args:
        user_id: Unique user identifier (mahasiswa_id or telegram user_id)
        daily_limit: Optional daily limit override (uses settings default if None)
        allow_on_failure: Preserve fallback behavior for callers that permit it.

    Returns:
        True if user is still under the daily limit and quota was incremented.
        False if user has reached the limit.
        
    Raises SupabaseServiceError when the quota is unavailable and
    allow_on_failure is False.
    """
    today = _get_current_date()
    settings = get_settings()
    
    # Use provided limit or fall back to settings
    limit = daily_limit if daily_limit is not None else settings.RATE_LIMIT_REQUESTS

    try:
        supabase = _get_supabase_client()
        response = supabase.rpc(
            "increment_quota_if_under_limit",
            {
                "p_user_id": str(user_id),
                "p_date": today,
                "p_daily_limit": limit,
            },
        ).execute()

        # Format 1: Scalar boolean (jika RPC mengembalikan boolean)
        if isinstance(response.data, bool):
            return response.data

        # Format 2: TABLE (allowed boolean, current_count integer) -> list[dict]
        if isinstance(response.data, list) and response.data:
            first_row = response.data[0]
            if isinstance(first_row, dict) and isinstance(first_row.get("allowed"), bool):
                return first_row["allowed"]

        raise ValueError("Invalid quota RPC response")
    except Exception as exc:
        logger.error("[quota] Daily quota check failed ({})", type(exc).__name__)
        if not allow_on_failure:
            raise SupabaseServiceError("Kuota harian tidak dapat diperiksa") from exc
        return True


def get_quota_status(user_id: str) -> dict[str, Any]:
    """
    Get current quota status for a user without incrementing.
    
    Returns:
        Dict with current count, limit, date, and remaining quota
    """
    today = _get_current_date()
    settings = get_settings()
    
    try:
        supabase = _get_supabase_client()
        response = supabase.table("user_quotas").select("message_count").eq("user_id", str(user_id)).eq("date", today).execute()
        
        current_count = 0
        if response.data:
            current_count = response.data[0]["message_count"]
        
        return {
            "user_id": str(user_id),
            "date": today,
            "current_count": current_count,
            "limit": settings.RATE_LIMIT_REQUESTS,
            "remaining": max(0, settings.RATE_LIMIT_REQUESTS - current_count)
        }
        
    except Exception as e:
        logger.error(f"[quota] Error getting quota status for user {user_id}: {e}")
        return {
            "user_id": str(user_id),
            "date": today,
            "current_count": 0,
            "limit": settings.RATE_LIMIT_REQUESTS,
            "remaining": settings.RATE_LIMIT_REQUESTS,
            "error": str(e)
        }
