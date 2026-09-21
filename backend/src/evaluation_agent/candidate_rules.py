"""Conservative rules for collecting RAG evaluation candidates automatically."""

from __future__ import annotations

from dataclasses import dataclass
import re

from src.monitoring.context import RequestMetricsCollector


@dataclass(frozen=True)
class AutoCandidateDecision:
    reason_code: str
    explanation: str


_ABSTENTION_PATTERNS = (
    re.compile(r"\bdokumen(?:\s+yang)?\s+saya\s+miliki\s+tidak\b", re.I),
    re.compile(r"\binformasi(?:\s+spesifik)?\s+tidak\s+(?:ada|tersedia|ditemukan)\b", re.I),
    re.compile(r"\btidak\s+(?:ditemukan|tersedia|tercantum|memuat)\b", re.I),
    re.compile(r"\bbelum\s+(?:ditemukan|tersedia)\b", re.I),
)


def is_abstention_answer(answer: str | None) -> bool:
    """Return whether a generated answer signals unavailable information.

    This is a review signal, not a correctness verdict. A source-grounded
    abstention can be the correct answer, but still deserves review when the
    document contains closely related information with a narrower scope.
    """
    normalized = " ".join((answer or "").split())
    return bool(normalized) and any(
        pattern.search(normalized) for pattern in _ABSTENTION_PATTERNS
    )


def detect_auto_candidate(
    collector: RequestMetricsCollector,
) -> AutoCandidateDecision | None:
    """Return a candidate when the pipeline exposes a useful review signal."""
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
        if collector.status == "success" and is_abstention_answer(collector.answer):
            return AutoCandidateDecision(
                reason_code="answer_abstention",
                explanation=(
                    "Ditambahkan otomatis karena jawaban menyatakan informasi "
                    "tidak tersedia. Tinjau apakah bukti terkait ada dengan "
                    "cakupan yang berbeda atau jawaban perlu diperjelas."
                ),
            )
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
