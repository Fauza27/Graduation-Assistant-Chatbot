"""
Persist RequestMetricsCollector ke tabel `request_metrics` di Supabase.

Pola sama seperti insert ke `chat_logs` yang sudah ada di
src/services/ai_services.py: sinkron, dibungkus try/except, TIDAK PERNAH
melempar exception ke pemanggil.
"""

from __future__ import annotations

from functools import lru_cache

from loguru import logger
from supabase import Client, create_client

from config.settings import get_settings
from src.monitoring.context import RequestMetricsCollector


@lru_cache(maxsize=1)
def _get_supabase_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


def persist_metrics(collector: RequestMetricsCollector) -> None:
    settings = get_settings()
    if not getattr(settings, "ENABLE_REQUEST_METRICS", True):
        return
    try:
        row = collector.to_row()
        _get_supabase_client().table("request_metrics").insert(row).execute()
    except Exception as e:
        logger.error(f"[metrics] Gagal menyimpan request_metrics request_id={collector.request_id}: {e}")


def persist_quota_rejection(
    session_id: str | None,
    channel: str,
    mahasiswa_id: str | None,
) -> None:
    """Catat baris minimal saat request ditolak KARENA KUOTA HARIAN HABIS
    (terjadi sebelum ai_services.chat() dipanggil, jadi butuh fungsi terpisah)."""
    settings = get_settings()
    if not getattr(settings, "ENABLE_REQUEST_METRICS", True):
        return
    try:
        _get_supabase_client().table("request_metrics").insert(
            {
                "session_id": session_id,
                "channel": channel,
                "mahasiswa_id": mahasiswa_id,
                "status": "quota_rejected",
                "total_ms": 0,
            }
        ).execute()
    except Exception as e:
        logger.error(f"[metrics] Gagal mencatat quota rejection untuk session {session_id}: {e}")