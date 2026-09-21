"""Deterministic first-pass root-cause classification for RAG traces."""

from __future__ import annotations

from src.evaluation_agent.models import ChunkAudit, Diagnosis, FailureStage


def _ids(rows: list[dict], field: str) -> set[str]:
    return {str(row.get(field, "")) for row in rows if row.get(field)}


def _rerank_gate_checks(trace: dict, audit: ChunkAudit) -> list[dict]:
    """Compute score/selection counterfactuals without mixing RRF score units."""
    rows = [
        row
        for row in trace.get("reranked_candidates", [])
        if row.get("score_source") == "cross_encoder"
        and isinstance(row.get("rerank_score"), (int, float))
    ]
    if not rows:
        return []
    top_score = max(row["rerank_score"] for row in rows)
    config = trace.get("pipeline_snapshot", {})
    relative_gap = config.get("rerank_relative_gap")
    minimum_top_score = config.get("rerank_min_top_score")
    coverage = {match.parent_id: match.coverage for match in audit.matches}
    return [
        {
            "parent_id": row["parent_id"],
            "evidence_coverage": coverage.get(row["parent_id"]),
            "rerank_rank": row.get("rank"),
            "rerank_score": row["rerank_score"],
            "top_rerank_score": top_score,
            "acceptance_threshold_at_request": (
                top_score - relative_gap
                if isinstance(relative_gap, (int, float))
                else None
            ),
            "top_score_passes_minimum_gate": (
                top_score >= minimum_top_score
                if isinstance(minimum_top_score, (int, float))
                else None
            ),
            "required_gap_if_scores_unchanged": round(
                top_score - row["rerank_score"], 6
            ),
            "required_top_n_if_order_unchanged": row.get("rank"),
            "request_relative_gap": config.get("rerank_relative_gap"),
            "request_top_n": config.get("rerank_top_n"),
            "truncated": row.get("rerank_truncated"),
            "selection_reason": row.get("selection_reason"),
        }
        for row in rows
        if row.get("parent_id") in audit.matched_parent_ids
    ]


def analyze_trace(
    *,
    answer_available: bool,
    chunk_audit: ChunkAudit,
    trace: dict | None,
    queue_reason: str = "manual_admin",
    has_related_scope_evidence: bool = False,
) -> Diagnosis:
    if not answer_available:
        if queue_reason == "answer_abstention" and has_related_scope_evidence:
            return Diagnosis(
                failed_stage=FailureStage.AMBIGUOUS,
                root_cause=(
                    "Dokumen asli memuat aturan terkait dengan cakupan yang "
                    "berbeda, tetapi tidak menjawab pertanyaan secara langsung. "
                    "Jawaban abstain perlu ditinjau dari kejelasan batas cakupannya."
                ),
                confidence=0.85,
                diagnostics={"queue_reason": queue_reason},
            )
        return Diagnosis(
            failed_stage=FailureStage.INFORMATION_UNAVAILABLE,
            root_cause="Informasi yang diperlukan tidak ditemukan dalam dokumen asli.",
            confidence=0.9,
            diagnostics={"queue_reason": queue_reason},
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
            diagnostics={
                "rerank_gate_checks": _rerank_gate_checks(trace, chunk_audit),
                "relevant_search_candidates": [
                    row
                    for row in trace.get("search_candidates", [])
                    if row.get("child_id") in relevant_children
                ],
                "relevant_parent_candidates": [
                    row
                    for row in trace.get("parent_candidates", [])
                    if row.get("parent_id") in relevant_parents
                ],
                "relevant_reranked_candidates": [
                    row for row in reranked if row.get("parent_id") in relevant_parents
                ],
                "parents_without_recorded_rerank_score": sorted(
                    relevant_parents.intersection(parent_candidates)
                    - _ids(reranked, "parent_id")
                ),
            },
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
