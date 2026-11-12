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
    return bool(getattr(settings, "ENABLE_REQUEST_METRICS", True))


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

        (_get_supabase_client().table("request_metrics").insert(row).execute())
        collector._persisted = True
        if settings.ENABLE_RESEARCH_REVIEW:
            persist_research_turn(collector, row["total_ms"])
        persist_execution_trace(collector)
        persist_auto_evaluation_candidate(collector)

    except Exception as exc:
        logger.error(
            "[metrics] Gagal menyimpan request_metrics "
            f"request_id={collector.request_id}: {exc}"
        )


def persist_research_turn(collector: RequestMetricsCollector, duration_ms: float) -> None:
    if (
        collector.channel != "website"
        or not collector.mahasiswa_id
        or not collector.session_id
        or not collector.question
        or collector.http_status in (400, 401, 403, 422)
    ):
        return

    success = collector.status == "success"
    try:
        _get_supabase_client().rpc(
            "record_research_turn",
            {
                "p_account": collector.mahasiswa_id,
                "p_request": collector.request_id,
                "p_started_at": collector._started_at.isoformat(),
                "p_session": collector.session_id,
                "p_question": collector.question,
                "p_answer": collector.answer if success else None,
                "p_sources": collector.response_sources if success else [],
                "p_status": collector.status,
                "p_http_status": collector.http_status,
                "p_error_source": collector.error_source,
                "p_total_ms": duration_ms,
            },
        ).execute()
    except Exception as exc:
        logger.error("Research capture failed for request {} ({})", collector.request_id, type(exc).__name__)


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


def persist_auto_evaluation_candidate(
    collector: RequestMetricsCollector,
) -> None:
    """Collect RAG failures and abstention responses without overriding review."""
    if not get_settings().EVALUATION_AGENT_ENABLED:
        return

    from src.evaluation_agent.candidate_rules import detect_auto_candidate

    decision = detect_auto_candidate(collector)
    if decision is None:
        return

    try:
        (
            _get_supabase_client()
            .table("evaluation_cases")
            .upsert(
                {
                    "request_id": collector.request_id,
                    "question": (collector.question or "").strip(),
                    "actual_answer": collector.answer,
                    "review_status": "unreviewed",
                    "queue_reason": decision.reason_code,
                    "review_notes": decision.explanation,
                    "created_by": f"system:auto:{decision.reason_code}",
                },
                on_conflict="request_id",
                ignore_duplicates=True,
            )
            .execute()
        )
    except Exception as exc:
        logger.error(
            "[metrics] Gagal menambahkan kandidat evaluasi otomatis "
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

        (_get_supabase_client().table("request_metrics").insert(row).execute())

    except Exception as exc:
        logger.error(
            "[metrics] Gagal mencatat quota rejection "
            f"untuk session {session_id}: {exc}"
        )
