"""
Shared quota management service for daily rate limiting.
"""

from datetime import datetime
from loguru import logger
from supabase import create_client, Client
from functools import lru_cache

from config.settings import get_settings


@lru_cache(maxsize=1)
def _get_supabase_client() -> Client:
    """Reuse single Supabase client instance across requests."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


def check_and_update_quota(user_id: str, daily_limit: int = None) -> bool:
    """
    Atomically increment quota and check daily limit via RPC.

    Args:
        user_id: Unique user identifier (mahasiswa_id or telegram user_id)
        daily_limit: Optional daily limit override (uses settings default if None)

    Returns:
        True if user is still under the daily limit and quota was incremented.
        False if user has reached the limit.
        
    Fail-open behavior: Returns True on DB errors to avoid blocking legitimate users.
    """
    today = datetime.now().strftime("%Y-%m-%d")
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

        # RPC returns boolean: True = allowed (and incremented), False = limit reached
        return bool(response.data)
        
    except Exception as e:
        logger.error(f"Error checking quota for user {user_id}: {e}")
        # Fail open to not block user on DB issues
        return True


def get_quota_status(user_id: str) -> dict:
    """
    Get current quota status for a user without incrementing.
    
    Returns:
        Dict with current count, limit, date, and remaining quota
    """
    today = datetime.now().strftime("%Y-%m-%d")
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
        logger.error(f"Error getting quota status for user {user_id}: {e}")
        return {
            "user_id": str(user_id),
            "date": today,
            "current_count": 0,
            "limit": settings.RATE_LIMIT_REQUESTS,
            "remaining": settings.RATE_LIMIT_REQUESTS,
            "error": str(e)
        }