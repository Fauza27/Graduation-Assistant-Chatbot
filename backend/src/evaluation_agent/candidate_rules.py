"""Conservative rules for collecting RAG failure candidates automatically."""

from __future__ import annotations

from dataclasses import dataclass

from src.monitoring.context import RequestMetricsCollector


@dataclass(frozen=True)
class AutoCandidateDecision:
    reason_code: str
    explanation: str


def detect_auto_candidate(
    collector: RequestMetricsCollector,
) -> AutoCandidateDecision | None:
    """Return a candidate only when the pipeline exposes a clear failure signal."""
    if not (collector.question or "").strip():
        return None

    if collector.status == "error" and collector.error_source == "retrieval":
        return AutoCandidateDecision(
            reason_code="retrieval_error",
            explanation=(
                "Ditambahkan otomatis karena retrieval pipeline mengalami error."
            ),
        )

    if collector.status != "success" or not collector.is_no_relevant_doc:
        return None

    if (collector.num_docs_retrieved or 0) > 0 and (
        collector.num_docs_after_rerank or 0
    ) == 0:
        return AutoCandidateDecision(
            reason_code="all_candidates_rejected",
            explanation=(
                "Ditambahkan otomatis karena kandidat ditemukan, tetapi semuanya "
                "ditolak sebelum pembuatan jawaban."
            ),
        )

    return AutoCandidateDecision(
        reason_code="no_relevant_document",
        explanation=(
            "Ditambahkan otomatis karena pipeline tidak menemukan dokumen relevan."
        ),
    )
