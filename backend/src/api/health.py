"""Health, readiness, and liveness endpoints."""

import asyncio
import platform
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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
    services: dict[str, Any]
    system: dict[str, Any]
    sessions: dict[str, Any]


HealthCheck = dict[str, Any]
HealthCheckFn = Callable[[], Awaitable[HealthCheck]]

_startup_time = time.time()


def _is_error_status(check_result: HealthCheck) -> bool:
    """True jika hasil satu health check berstatus error."""
    return check_result.get("status") == "error"


@router.get("/", response_model=HealthStatus)
async def basic_health_check(settings: Settings = Depends(get_settings)):
    """Return basic application health information."""
    return HealthStatus(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        uptime_seconds=_uptime_seconds(),
    )


@router.get("/detailed", response_model=DetailedHealthStatus)
async def detailed_health_check(settings: Settings = Depends(get_settings)):
    """Return health information for external dependencies and local state."""

    openai_status, supabase_status = await asyncio.gather(
        _check_openai_health(settings),
        _check_supabase_health(settings),
    )

    services = {
        "openai": openai_status,
        "supabase": supabase_status,
        "telegram_bot": _telegram_health(settings),
    }
    overall_status = (
        "degraded" if any(_is_error_status(service) for service in services.values())
        else "healthy"
    )

    return DetailedHealthStatus(
        status=overall_status,
        timestamp=datetime.now(timezone.utc),
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        uptime_seconds=_uptime_seconds(),
        services=services,
        system={
            "python_version": platform.python_version(),
            "max_concurrent_requests": settings.MAX_CONCURRENT_REQUESTS,
            "rate_limit_per_day": settings.RATE_LIMIT_REQUESTS,
        },
        sessions=get_session_stats(),
    )


def _uptime_seconds() -> float:
    return time.time() - _startup_time


def _telegram_health(settings: Settings) -> HealthCheck:
    return {
        "status": "configured" if settings.TELEGRAM_BOT_TOKEN else "not_configured"
    }


async def _run_health_check(check_fn: HealthCheckFn) -> HealthCheck:
    """Run one check and return a stable success or error payload."""
    try:
        started_at = time.perf_counter()
        extra_info = await check_fn()
        response_time_ms = round((time.perf_counter() - started_at) * 1000, 2)
        return {"status": "healthy", "response_time_ms": response_time_ms, **extra_info}
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "error_type": type(exc).__name__,
        }


async def _check_openai_health(settings: Settings) -> HealthCheck:
    """Check the OpenAI API using the configured generation model."""
    async def _ping() -> HealthCheck:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(**settings.get_openai_config())
        try:
            model = await client.models.retrieve(settings.llm_model)
            return {"model": model.id}
        finally:
            await client.close()

    return await _run_health_check(_ping)


async def _check_supabase_health(settings: Settings) -> HealthCheck:
    """Check Supabase without blocking FastAPI's event loop."""
    async def _ping() -> HealthCheck:
        from supabase import create_client

        cfg = settings.get_supabase_config()
        result = await asyncio.to_thread(
            lambda: (
                create_client(cfg["url"], cfg["key"])
                .table(settings.table_parent_chunks)
                .select("parent_id")
                .limit(1)
                .execute()
            )
        )
        return {
            "healthy": True,
            "data": result.data,
        }

    return await _run_health_check(_ping)

@router.get("/readiness")
async def readiness_check(settings: Settings = Depends(get_settings)):
    """Return 503 when a critical dependency is unavailable."""

    openai_status, supabase_status = await asyncio.gather(
        _check_openai_health(settings),
        _check_supabase_health(settings),
    )
    checks = {"openai": openai_status, "supabase": supabase_status}

    for service_name, status in checks.items():
        if _is_error_status(status):
            raise HTTPException(
                status_code=503,
                detail=f"Service {service_name} is not ready: {status.get('error', 'Unknown error')}"
            )

    return {"status": "ready", "timestamp": datetime.now(timezone.utc)}


@router.get("/liveness")
async def liveness_check():
    """Return whether the FastAPI process is alive."""
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc),
        "uptime_seconds": _uptime_seconds(),
    }
