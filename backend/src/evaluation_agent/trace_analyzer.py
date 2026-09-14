"""Deterministic first-pass root-cause classification for RAG traces."""

from __future__ import annotations

from src.evaluation_agent.models import ChunkAudit, Diagnosis, FailureStage


def _ids(rows: list[dict], field: str) -> set[str]:
    return {str(row.get(field, "")) for row in rows if row.get(field)}


def analyze_trace(
    *,
    answer_available: bool,
    chunk_audit: ChunkAudit,
    trace: dict | None,
) -> Diagnosis:
    if not answer_available:
        return Diagnosis(
            failed_stage=FailureStage.INFORMATION_UNAVAILABLE,
            root_cause="Informasi yang diperlukan tidak ditemukan dalam dokumen asli.",
            confidence=0.9,
        )

    if chunk_audit.status.startswith("extraction"):
        return Diagnosis(
            failed_stage=FailureStage.EXTRACTION,
            root_cause=chunk_audit.explanation,
            confidence=0.85,
            diagnostics=chunk_audit.diagnostics,
        )
    if chunk_audit.status != "chunking_valid":
        return Diagnosis(
            failed_stage=FailureStage.CHUNKING,
            root_cause=chunk_audit.explanation,
            confidence=0.8,
            diagnostics=chunk_audit.diagnostics,
        )
    if not trace:
        return Diagnosis(
            failed_stage=FailureStage.UNKNOWN,
            root_cause="Trace pipeline tidak tersedia untuk request ini.",
            confidence=0.3,
        )

    relevant_children = set(chunk_audit.affected_chunk_ids)
    relevant_parents = set(chunk_audit.matched_parent_ids)
    search_children = _ids(trace.get("search_candidates", []), "child_id")
    parent_candidates = _ids(trace.get("parent_candidates", []), "parent_id")
    reranked = trace.get("reranked_candidates", [])
    accepted_parents = {
        str(row.get("parent_id", "")) for row in reranked if row.get("accepted")
    }
    context_parents = set(trace.get("final_context", {}).get("document_ids", []))

    if relevant_children.isdisjoint(search_children):
        self_queries = trace.get("self_query_results", [])
        filters_used = [item.get("filters", {}) for item in self_queries]
        has_filters = any(filters_used)
        return Diagnosis(
            failed_stage=(
                FailureStage.QUERY_PROCESSING if has_filters else FailureStage.RETRIEVAL
            ),
            root_cause=(
                "Filter hasil pemrosesan query tidak membawa chunk bukti ke hasil pencarian."
                if has_filters
                else "Chunk yang memuat bukti tidak ditemukan oleh hybrid retrieval."
            ),
            confidence=0.82,
            diagnostics={"filters": filters_used},
        )
    if relevant_parents.isdisjoint(parent_candidates):
        return Diagnosis(
            failed_stage=FailureStage.PARENT_ASSEMBLY,
            root_cause="Child relevan ditemukan, tetapi parent-nya tidak menjadi kandidat.",
            confidence=0.9,
        )
    if relevant_parents.isdisjoint(accepted_parents):
        return Diagnosis(
            failed_stage=FailureStage.RERANKING,
            root_cause="Parent relevan tersedia sebelum reranker tetapi tidak diterima.",
            confidence=0.9,
        )
    if relevant_parents.isdisjoint(context_parents):
        return Diagnosis(
            failed_stage=FailureStage.CONTEXT_ASSEMBLY,
            root_cause="Parent relevan diterima tetapi tidak tercatat dalam context akhir.",
            confidence=0.9,
        )
    return Diagnosis(
        failed_stage=FailureStage.GENERATION,
        root_cause="Bukti tersedia dalam context akhir, tetapi jawaban dinilai gagal.",
        confidence=0.85,
    )
