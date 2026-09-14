"""
Health check endpoints for monitoring system status
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Callable, Awaitable
import time
import asyncio
import platform
from datetime import datetime, timezone
 
from config.settings import get_settings, Settings
from src.services.ai_services import get_session_stats

router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    status: str
    timestamp: datetime
    version: str
    environment: str
    uptime_seconds: float
 
 
class DetailedHealthStatus(HealthStatus):
    services: Dict[str, Any]
    system: Dict[str, Any]
    sessions: Dict[str, Any]

# Track startup time for uptime calculation
_startup_time = time.time()

def _is_error_status(check_result: Dict[str, Any]) -> bool:
    """True jika hasil satu health check berstatus error."""
    return check_result.get("status") == "error"


@router.get("/", response_model=HealthStatus)
async def basic_health_check(settings: Settings = Depends(get_settings)):
    """Basic health check endpoint"""
    return HealthStatus(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        uptime_seconds=time.time() - _startup_time
    )


@router.get("/detailed", response_model=DetailedHealthStatus)
async def detailed_health_check(settings: Settings = Depends(get_settings)):
    """Detailed health check with service status"""
 
    openai_status, supabase_status = await asyncio.gather(
        _check_openai_health(settings),
        _check_supabase_health(settings),
    )
 
    session_stats = get_session_stats()
 
    system_info = {
        "python_version": platform.python_version(),
        "max_concurrent_requests": settings.MAX_CONCURRENT_REQUESTS,
        "rate_limit_per_day": settings.RATE_LIMIT_REQUESTS,
    }
 
    services = {
        "openai": openai_status,
        "supabase": supabase_status,
        "telegram_bot": {"status": "configured" if settings.TELEGRAM_BOT_TOKEN else "not_configured"}
    }
 
    overall_status = "degraded" if any(_is_error_status(s) for s in services.values()) else "healthy"
 
    return DetailedHealthStatus(
        status=overall_status,
        timestamp=datetime.now(timezone.utc),
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        uptime_seconds=time.time() - _startup_time,
        services=services,
        system=system_info,
        sessions=session_stats
    )

async def _run_health_check(check_fn: Callable[[], Awaitable[Dict[str, Any]]]) -> Dict[str, Any]:
    """Jalankan satu health check, ukur response time, dan seragamkan hasil:
    sukses -> {status: healthy, response_time_ms, ...info}
    gagal  -> {status: error, error, error_type}
    Menghindari duplikasi try/except+timing di tiap fungsi check service."""
    try:
        start_time = time.time()
        extra_info = await check_fn()
        response_time_ms = round((time.time() - start_time) * 1000, 2)
        return {"status": "healthy", "response_time_ms": response_time_ms, **extra_info}
    except Exception as e:
        return {"status": "error", "error": str(e), "error_type": type(e).__name__}


async def _check_openai_health(settings: Settings) -> Dict[str, Any]:
    """Check OpenAI API connectivity"""
    async def _ping() -> Dict[str, Any]:
        from openai import AsyncOpenAI
 
        client = AsyncOpenAI(**settings.get_openai_config())
        # Use actual production model instead of hardcoded "gpt-5"
        model = await client.models.retrieve(settings.llm_model)
        return {"model": model.id}
 
    return await _run_health_check(_ping)

async def _check_supabase_health(settings: Settings) -> Dict[str, Any]:
    """Check Supabase connectivity"""
    async def _ping() -> Dict[str, Any]:
        from supabase import create_client
 
        cfg = settings.get_supabase_config()
        supabase = create_client(cfg["url"], cfg["key"])
        result = (
            supabase
            .table(settings.table_parent_chunks)
            .select("parent_id")
            .limit(1)
            .execute()
        )
        return {
            "healthy": True,
            "data": result.data,
        }
 
    return await _run_health_check(_ping)

@router.get("/readiness")
async def readiness_check(settings: Settings = Depends(get_settings)):
    """Kubernetes-style readiness probe"""
 
    openai_status, supabase_status = await asyncio.gather(
        _check_openai_health(settings),
        _check_supabase_health(settings),
    )
    checks = {"openai": openai_status, "supabase": supabase_status}
 
    # Jika ada service kritikal yang error, kembalikan 503
    for service_name, status in checks.items():
        if _is_error_status(status):
            raise HTTPException(
                status_code=503,
                detail=f"Service {service_name} is not ready: {status.get('error', 'Unknown error')}"
            )
 
    return {"status": "ready", "timestamp": datetime.now(timezone.utc)}

@router.get("/liveness")
async def liveness_check():
    """Kubernetes-style liveness probe"""
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc),
        "uptime_seconds": time.time() - _startup_time
    }