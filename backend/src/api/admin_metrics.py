"""
Endpoint admin untuk membaca hasil agregasi monitoring (views dari Fase 7).
Semua endpoint di sini read-only dan butuh autentikasi admin.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from supabase import Client, create_client

from config.settings import get_settings
from src.admin.auth import get_current_admin

router = APIRouter(prefix="/admin/metrics", tags=["Admin Metrics"])


@lru_cache(maxsize=1)
def _get_supabase_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


def _select_view(view_name: str, days: int, order_col: str = "day") -> dict[str, Any]:
    """
    Select data from view with date filtering.
    
    Returns dict with data and metadata about filtering success.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    client = _get_supabase_client()
    query = client.table(view_name).select("*")
    
    date_filter_applied = True
    filter_error = None
    
    try:
        query = query.gte(order_col, since)
    except Exception as exc:
        date_filter_applied = False
        filter_error = str(exc)
        logger.warning(
            f"Failed to apply date filter on view '{view_name}' "
            f"with column '{order_col}': {exc}. "
            f"Returning unfiltered data (may be large dataset)"
        )
    
    response = query.execute()
    
    return {
        "data": response.data or [],
        "metadata": {
            "date_filter_applied": date_filter_applied,
            "filter_error": filter_error,
            "requested_days": days,
            "total_records": len(response.data or [])
        }
    }


@router.get("/latency", summary="A1/A3: latency percentile & throughput per jam")
async def get_latency_stats(days: int = Query(default=7, ge=1, le=90), admin: dict = Depends(get_current_admin)):
    result = _select_view("v_latency_stats_hourly", days, order_col="bucket")
    return {
        "data": result["data"],
        "date_filter_applied": result["metadata"]["date_filter_applied"],
        "total_records": result["metadata"]["total_records"]
    }


@router.get("/stage-breakdown", summary="A2: rata-rata durasi tiap tahap pipeline per hari")
async def get_stage_breakdown(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_stage_breakdown_daily", days)}


@router.get("/errors", summary="B1/B4: error rate & quota rejection rate per hari")
async def get_error_stats(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_error_stats_daily", days)}


@router.get("/errors/breakdown", summary="B2: breakdown error by source")
async def get_error_breakdown(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_error_breakdown_daily", days)}


@router.get("/openai-retry", summary="B3: retry rate ke OpenAI")
async def get_openai_retry_stats(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_openai_retry_stats_daily", days)}


@router.get("/retrieval-quality", summary="C1/C3/C4: kualitas retrieval per hari")
async def get_retrieval_quality(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_retrieval_quality_daily", days)}


@router.get("/top-documents", summary="C2: dokumen paling sering diambil")
async def get_top_documents(limit: int = Query(default=20, ge=1, le=100), admin: dict = Depends(get_current_admin)):
    try:
        client = _get_supabase_client()
        response = client.table("v_top_retrieved_documents").select("*").limit(limit).execute()
        return {"data": response.data or []}
    except Exception as exc:
        logger.error(f"Failed to fetch top documents (limit={limit}): {exc}")
        return {
            "error": f"Failed to fetch top documents: {str(exc)}",
            "data": [],
            "troubleshooting": {
                "check_view_exists": "v_top_retrieved_documents",
                "requested_limit": limit
            }
        }


@router.get("/domain-stats", summary="C5: breakdown query per domain")
async def get_domain_stats(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_domain_stats_daily", days)}


@router.get("/cost", summary="D2/D3: cost harian & cost per request")
async def get_cost_stats(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_cost_daily", days)}


@router.get("/cost/per-user", summary="D3: cost per user")
async def get_cost_per_user(limit: int = Query(default=50, ge=1, le=500), admin: dict = Depends(get_current_admin)):
    try:
        client = _get_supabase_client()
        response = client.table("v_cost_per_user").select("*").limit(limit).execute()
        return {"data": response.data or []}
    except Exception as exc:
        logger.error(f"Failed to fetch cost per user (limit={limit}): {exc}")
        return {
            "error": f"Failed to fetch cost per user: {str(exc)}",
            "data": [],
            "troubleshooting": {
                "check_view_exists": "v_cost_per_user",
                "requested_limit": limit
            }
        }


@router.get("/usage/active-users", summary="E1: active users harian/bulanan per channel")
async def get_active_users(
    granularity: str = Query(default="daily", pattern="^(daily|monthly)$"),
    days: int = Query(default=30, ge=1, le=365),
    admin: dict = Depends(get_current_admin)
):
    view_name = f"v_active_users_{granularity}"
    return {"data": _select_view(view_name, days, order_col="day" if granularity == "daily" else "month")}


@router.get("/usage/new-vs-returning", summary="E2: sesi baru vs lanjutan per hari")
async def get_new_vs_returning(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_new_vs_returning_daily", days)}


@router.get("/usage/turns-per-session", summary="E2: rata-rata turn per sesi per hari")
async def get_turns_per_session(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_avg_turns_per_session_daily", days)}


@router.get("/usage/followup-rate", summary="E5: repeat/follow-up question rate")
async def get_followup_rate(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_followup_rate_daily", days)}


@router.get("/system", summary="F1: active session count vs MAX_ACTIVE_SESSIONS")
async def get_system_health(admin: dict = Depends(get_current_admin)):
    try:
        from src.services.ai_services import get_session_stats

        settings = get_settings()
        stats = get_session_stats()
        active = stats.get("active_sessions") or stats.get("total_sessions") or 0
        max_sessions = settings.MAX_ACTIVE_SESSIONS
        return {
            "session_stats": stats,
            "max_active_sessions": max_sessions,
            "utilization_pct": round(100.0 * active / max_sessions, 2) if max_sessions else None,
        }
    except Exception as exc:
        logger.error(f"Failed to fetch system health metrics: {exc}")
        return {
            "error": f"Failed to fetch system health: {str(exc)}",
            "session_stats": {},
            "max_active_sessions": None,
            "utilization_pct": None,
        }


@router.get("/admin-activity", summary="F3: aktivitas admin (chunk edit + re-embed)")
async def get_admin_activity(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_admin_activity_daily", days)}


@router.get("/system/overview", summary="Dashboard overview dengan key metrics")
async def get_system_overview(days: int = Query(default=7, ge=1, le=30), admin: dict = Depends(get_current_admin)):
    """Endpoint khusus untuk dashboard overview yang menggabungkan beberapa metrics utama."""
    client = _get_supabase_client()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    try:
        # Total requests dalam periode
        total_requests = client.table("request_metrics").select("*", count="exact").gte("created_at", since).execute()
        
        # Success rate
        success_requests = client.table("request_metrics").select("*", count="exact").eq("status", "success").gte("created_at", since).execute()
        
        # Average latency
        latency_stats = client.table("request_metrics").select("total_ms").eq("status", "success").gte("created_at", since).execute()
        
        # Total cost
        cost_stats = client.table("request_metrics").select("llm_cost_usd,embedding_cost_usd").eq("status", "success").gte("created_at", since).execute()
        
        # Active users
        active_users = client.table("request_metrics").select("mahasiswa_id,session_id").eq("status", "success").gte("created_at", since).execute()
        
        # Calculate metrics
        total_count = total_requests.count or 0
        success_count = success_requests.count or 0
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
        latencies = [r["total_ms"] for r in (latency_stats.data or []) if r.get("total_ms") is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        total_cost = sum(
            (r.get("llm_cost_usd") or 0) + (r.get("embedding_cost_usd") or 0)
            for r in (cost_stats.data or [])
        )
        
        unique_users = len(set(
            r.get("mahasiswa_id") or r.get("session_id") 
            for r in (active_users.data or [])
            if r.get("mahasiswa_id") or r.get("session_id")
        ))
        
        return {
            "data": {
                "period_days": days,
                "total_requests": total_count,
                "success_rate_pct": round(success_rate, 2),
                "avg_latency_ms": round(avg_latency, 2),
                "total_cost_usd": round(total_cost, 6),
                "active_users": unique_users,
            }
        }
    except Exception as e:
        # Log the actual error for debugging instead of generic message
        logger.error(f"Failed to fetch system overview metrics for {days} days: {str(e)}")
        return {
            "error": f"Failed to fetch overview: {str(e)}", 
            "data": None,
            "troubleshooting": {
                "check_database_connection": True,
                "verify_request_metrics_table": True,
                "period_days_requested": days,
                "since_timestamp": since
            }
        }


# ============================================================
# Investigasi & drill-down — dipakai oleh dashboard Monitoring
# untuk fitur "klik lebih dalam": ranking latency per tahap,
# detail 1 request, histori lengkap, list error dengan user,
# list pertanyaan per domain/no-relevant-doc, detail cross-encoder.
#
# Desain: SATU endpoint list mentah (`/query-log`) dipakai untuk semua
# variasi filter/urut/paginasi di sisi frontend (mengikuti pola query log
# terpadu di mockup), plus SATU endpoint detail (`/request/{id}`) yang juga
# menyertakan `retrieval_detail` (skor cross-encoder per dokumen kandidat).
# ============================================================

_QUERY_LOG_FIELDS = (
    "request_id,created_at,session_id,mahasiswa_id,username,channel,question,"
    "domain_detected,status,error_source,error_type,total_ms,"
    "stage_validation_ms,stage_session_load_ms,stage_reformulation_ms,"
    "stage_embedding_ms,stage_retrieval_ms,stage_reranking_ms,"
    "stage_parent_assembly_ms,stage_generation_ms,stage_db_save_ms,"
    "num_docs_retrieved,num_docs_after_rerank,top_cross_encoder_score,"
    "avg_cross_encoder_score,is_no_relevant_doc"
)


@router.get("/query-log", summary="Investigasi: daftar mentah request untuk drill-down (klik tahap/error/domain/dsb)")
async def get_query_log(
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=500, ge=1, le=2000),
    admin: dict = Depends(get_current_admin),
):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    client = _get_supabase_client()
    response = (
        client.table("request_metrics")
        .select(_QUERY_LOG_FIELDS)
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"data": response.data or []}


@router.get("/request/{request_id}", summary="Investigasi: detail lengkap satu request (semua tahap, token, cost, retrieval_detail)")
async def get_request_detail(request_id: str, admin: dict = Depends(get_current_admin)):
    client = _get_supabase_client()
    response = client.table("request_metrics").select("*").eq("request_id", request_id).limit(1).execute()
    rows = response.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="request_id tidak ditemukan")
    return {"data": rows[0]}