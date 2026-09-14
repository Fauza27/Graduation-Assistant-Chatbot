"""
Persist RequestMetricsCollector ke tabel `request_metrics` di Supabase.

Pola sama seperti insert ke `chat_logs` yang sudah ada di
src/services/ai_services.py: sinkron, dibungkus try/except, dan
TIDAK PERNAH melempar exception ke pemanggil.

Kegagalan menyimpan metrics tidak boleh mengganggu alur chat utama.
"""

from __future__ import annotations

from functools import lru_cache

from loguru import logger
from supabase import Client, create_client

from config.settings import Settings, get_settings
from src.monitoring.context import RequestMetricsCollector, get_current


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_supabase_client() -> Client:
    """Return cached Supabase client."""
    settings = get_settings()

    return create_client(
        settings.supabase_url,
        settings.supabase_service_key,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _metrics_enabled(settings: Settings) -> bool:
    """Return apakah request metrics diaktifkan."""
    return bool(
        getattr(settings, "ENABLE_REQUEST_METRICS", True)
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def persist_metrics(collector: RequestMetricsCollector) -> None:
    """
    Persist collector ke tabel request_metrics.

    Error sengaja ditelan agar monitoring tidak pernah memblokir
    alur aplikasi utama.
    """
    if getattr(collector, "_persisted", False):
        return

    try:
        settings = get_settings()

        if not _metrics_enabled(settings):
            return

        row = collector.to_row()

        (
            _get_supabase_client()
            .table("request_metrics")
            .insert(row)
            .execute()
        )
        collector._persisted = True
        persist_execution_trace(collector)

    except Exception as exc:
        logger.error(
            "[metrics] Gagal menyimpan request_metrics "
            f"request_id={collector.request_id}: {exc}"
        )


def persist_execution_trace(collector: RequestMetricsCollector) -> None:
    """Persist detailed trace without ever interrupting the chat request."""
    if not get_settings().EVALUATION_AGENT_ENABLED:
        return
    if getattr(collector, "_trace_persisted", False):
        return

    try:
        (
            _get_supabase_client()
            .table("rag_execution_traces")
            .upsert(collector.to_trace_row(), on_conflict="request_id")
            .execute()
        )
        collector._trace_persisted = True
    except Exception as exc:
        logger.error(
            "[metrics] Gagal menyimpan rag_execution_traces "
            f"request_id={collector.request_id}: {exc}"
        )


def persist_quota_rejection(
    session_id: str | None,
    channel: str,
    mahasiswa_id: str | None,
) -> None:
    """
    Persist quota rejection.

    Jalur A:
        collector aktif -> update collector -> persist.

    Jalur B:
        tidak ada collector aktif -> buat collector minimal -> persist.
    """
    collector = get_current()

    # ---------------------------------------------------------------------
    # Jalur A: collector aktif
    # ---------------------------------------------------------------------
    if collector is not None:
        collector.status = "quota_rejected"
        collector.http_status = 429
        persist_metrics(collector)
        return

    # ---------------------------------------------------------------------
    # Jalur B: collector belum tersedia
    # ---------------------------------------------------------------------
    try:
        settings = get_settings()

        if not _metrics_enabled(settings):
            return

        fallback_collector = RequestMetricsCollector(
            session_id=session_id,
            channel=channel,
            mahasiswa_id=mahasiswa_id,
            status="quota_rejected",
            http_status=429,
        )

        row = fallback_collector.to_row()

        (
            _get_supabase_client()
            .table("request_metrics")
            .insert(row)
            .execute()
        )

    except Exception as exc:
        logger.error(
            "[metrics] Gagal mencatat quota rejection "
            f"untuk session {session_id}: {exc}"
        )
