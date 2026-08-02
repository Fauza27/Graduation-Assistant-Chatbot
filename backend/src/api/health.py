"""
Health check endpoints for monitoring system status
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
import time
import asyncio
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
    
    # Check OpenAI connectivity
    openai_status = await _check_openai_health(settings)
    
    # Check Supabase connectivity
    supabase_status = await _check_supabase_health(settings)
    
    # Get session statistics
    session_stats = get_session_stats()
    
    # System information
    system_info = {
        "python_version": "3.9+",
        "max_concurrent_requests": settings.MAX_CONCURRENT_REQUESTS,
        "rate_limit_per_day": settings.RATE_LIMIT_REQUESTS,
    }
    
    services = {
        "openai": openai_status,
        "supabase": supabase_status,
        "telegram_bot": {"status": "configured" if settings.TELEGRAM_BOT_TOKEN else "not_configured"}
    }
    
    # Determine overall status
    overall_status = "healthy"
    if any(service.get("status") == "error" for service in services.values()):
        overall_status = "degraded"
    
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


async def _check_openai_health(settings: Settings) -> Dict[str, Any]:
    """Check OpenAI API connectivity"""
    try:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(**settings.get_openai_config())
        
        # Simple API call to check connectivity
        start_time = time.time()
        models = await client.models.list()
        response_time = time.time() - start_time
        
        return {
            "status": "healthy",
            "response_time_ms": round(response_time * 1000, 2),
            "model_count": len(models.data) if models.data else 0
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }


async def _check_supabase_health(settings: Settings) -> Dict[str, Any]:
    """Check Supabase connectivity"""
    try:
        from supabase import create_client
        
        supabase = create_client(**settings.get_supabase_config())
        
        # Simple query to check connectivity
        start_time = time.time()
        result = supabase.table(settings.table_parent_chunks).select("count", count="exact").limit(1).execute()
        response_time = time.time() - start_time
        
        return {
            "status": "healthy",
            "response_time_ms": round(response_time * 1000, 2),
            "document_count": result.count if hasattr(result, 'count') else "unknown"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }


@router.get("/readiness")
async def readiness_check(settings: Settings = Depends(get_settings)):
    """Kubernetes-style readiness probe"""
    
    # Check critical dependencies
    checks = {
        "openai": await _check_openai_health(settings),
        "supabase": await _check_supabase_health(settings),
    }
    
    # If any critical service is down, return 503
    for service_name, status in checks.items():
        if status.get("status") == "error":
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