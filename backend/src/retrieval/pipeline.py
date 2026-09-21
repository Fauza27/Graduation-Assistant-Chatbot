"""Single source of truth for the RAG retrieval pipeline.

Pipeline:
    self-query → hybrid search → parent fetching → reranking

Features:
    - Candidate limiting
    - Adaptive reranking
    - Zero-document short-circuit
    - Structured fallback on retrieval errors
    - Retrieval metrics and profiling
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from config.settings import get_settings
from src.monitoring.context import end_stage, set_field, start_stage
from src.monitoring.errors import RetrievalError
from src.security.content_safety import text_for_log

if TYPE_CHECKING:
    from src.retrieval.hybrid_search import HybridSearchResult


MULTI_QUERY_RRF_K = 60


# ============================================================================
# Result model
# ============================================================================


@dataclass
class RetrievalResult:
    """Final retrieval result ready for the answer generator."""

    parent_documents: list[dict]
    is_empty: bool

    @property
    def num_docs(self) -> int:
        """Number of retrieved parent documents."""

        return len(self.parent_documents)


# ============================================================================
# Main pipeline
# ============================================================================


def run_retrieval(
    query: str,
    rerank_query: str | None = None,
    search_queries: tuple[str, ...] | list[str] | None = None,
) -> RetrievalResult:
    """
    Run the complete retrieval pipeline for one query.

    Args:
        query:
            Semantic retrieval query. Normally this is the reformulated
            query when conversation context requires it.

        rerank_query:
            Query used by the cross-encoder reranker. Defaults to `query`.
            Usually the original user question is preferable here.

        search_queries:
            Query variants from QueryPlan. Multi-query execution is handled
            by this pipeline; the first query remains the primary fallback.
    """

    from src.retrieval.reranker import CrossEncoderReranker
    from src.retrieval.self_query import (
        ParsedQuery,
        extract_query_components,
    )
    from src.retrieval.source_utils import detect_panduan_type
    from src.services.ai_services import _get_hybrid_searcher, _get_parent_child_fetcher

    settings = get_settings()
    rerank_query = rerank_query or query
    planned_queries = _normalize_search_queries(query, search_queries)
    query = planned_queries[0]
    pipeline_start = time.time()

    # ------------------------------------------------------------------
    # Stage 1: Self-query parsing
    # ------------------------------------------------------------------

    start_stage("self_query")
    started_at = time.time()

    parsed_queries: list[ParsedQuery] = []
    for planned_query in planned_queries:
        try:
            parsed_queries.append(extract_query_components(planned_query))
        except Exception as exc:
            logger.error("Error in extract_query_components: {}", exc)
            parsed_queries.append(
                ParsedQuery(
                    semantic_query=planned_query,
                    filters={},
                    original_query=planned_query,
                    confidence="low",
                )
            )

    parse_time = time.time() - started_at
    end_stage()

    _record_detected_domains(
        parsed_queries,
        detect_panduan_type,
    )
    set_field(
        self_query_results=[
            {
                "original_query": parsed.original_query,
                "semantic_query": parsed.semantic_query,
                "filters": dict(parsed.filters),
                "detected_source": parsed.detected_source,
                "detected_section": parsed.detected_section,
                "confidence": parsed.confidence,
            }
            for parsed in parsed_queries
        ]
    )

    # ------------------------------------------------------------------
    # Stage 2: Hybrid search
    # ------------------------------------------------------------------

    started_at = time.time()

    search_batches: list[list[HybridSearchResult]] = []
    matched_queries: dict[str, set[str]] = {}
    search_errors: list[Exception] = []
    searcher = _get_hybrid_searcher()

    for parsed in parsed_queries:
        try:
            batch = searcher.search(
                query=parsed.semantic_query,
                filters=parsed.filters,
            )
            search_batches.append(batch)
            for candidate in batch:
                matched_queries.setdefault(candidate.child_id, set()).add(
                    parsed.semantic_query
                )
        except Exception as exc:
            logger.error(
                "Error in HybridSearcher.search for '{}': {}",
                text_for_log(parsed.semantic_query),
                exc,
            )
            search_errors.append(exc)

    if search_errors and len(search_errors) == len(parsed_queries):
        raise RetrievalError(
            "Seluruh pencarian retrieval gagal karena dependency tidak tersedia"
        ) from search_errors[-1]

    search_results = _deduplicate_equivalent_child_content(
        _merge_search_results(search_batches)
    )
    set_field(
        num_docs_retrieved=len(search_results),
        search_candidates=_serialize_search_candidates(
            search_results, matched_queries=matched_queries
        ),
    )

    search_time = time.time() - started_at

    if not search_results:
        logger.info("Zero documents found in Hybrid Search. " "Short-circuiting.")

        _record_empty_retrieval_metrics()

        return RetrievalResult(
            parent_documents=[],
            is_empty=True,
        )

    # ------------------------------------------------------------------
    # Stage 3: Parent document assembly
    # ------------------------------------------------------------------

    start_stage("parent_assembly")
    started_at = time.time()

    try:
        parent_results = _get_parent_child_fetcher().fetch_parents(search_results)
    except Exception as exc:
        logger.error(
            "Error in ParentChildFetcher.fetch_parents: {}",
            exc,
        )
        raise RetrievalError("Gagal mengambil parent documents") from exc

    fetch_time = time.time() - started_at
    end_stage()

    if not parent_results:
        logger.info("Zero parent documents fetched. " "Short-circuiting.")

        _record_empty_retrieval_metrics()

        return RetrievalResult(
            parent_documents=[],
            is_empty=True,
        )

    # ------------------------------------------------------------------
    # Stage 4: Limit candidates before reranking
    # ------------------------------------------------------------------

    candidate_parents = parent_results[: settings.max_parent_for_rerank]
    set_field(parent_candidates=_serialize_parent_candidates(parent_results))

    logger.debug(
        "Reranking candidates: {} → {}",
        len(parent_results),
        len(candidate_parents),
    )

    # ------------------------------------------------------------------
    # Stage 5: Adaptive reranking
    # ------------------------------------------------------------------

    if len(candidate_parents) <= settings.min_parent_for_rerank:
        final_results = _skip_reranking(
            candidate_parents,
            settings.rerank_top_n,
        )

        rerank_time = 0.0
        reason = "Reranking Skipped"

        _log_pipeline_summary(
            pipeline_start=pipeline_start,
            parse_time=parse_time,
            search_time=search_time,
            fetch_time=fetch_time,
            rerank_time=rerank_time,
            candidate_count=len(candidate_parents),
            final_results=final_results,
            reason=reason,
        )

        _record_final_retrieval_metrics(
            final_results,
            all_scored_candidates=candidate_parents,
        )
        set_field(reranked_candidates=_serialize_parent_candidates(final_results))

        return RetrievalResult(
            parent_documents=final_results,
            is_empty=not final_results,
        )

    # ------------------------------------------------------------------
    # Stage 5B: Cross-encoder reranking
    # ------------------------------------------------------------------

    start_stage("reranking")
    started_at = time.time()

    reranked: list[dict] = []
    final_results: list[dict] = []
    reason = ""
    top_score = 0.0

    try:
        reranked = CrossEncoderReranker().rerank(
            query=rerank_query,
            documents=candidate_parents,
            # Keep every scored candidate for diagnosis. Final selection still
            # applies rerank_top_n below, so retrieval behavior is unchanged.
            top_n=len(candidate_parents),
        )

        for document in reranked:
            document["score_source"] = "cross_encoder"
            document["rerank_method"] = "cross_encoder"

        final_results, reason, top_score = _select_reranked_documents(
            reranked, settings
        )

    except Exception as exc:
        logger.warning(
            "Reranking failed, using unranked top-N: {}",
            exc,
        )

        final_results = [
            dict(document) for document in candidate_parents[: settings.rerank_top_n]
        ]

        for document in final_results:
            document["cross_encoder_score"] = document.get(
                "best_child_score",
                0.0,
            )
            document["score_source"] = "hybrid_fallback"
            document["rerank_method"] = "fallback"

        top_score = (
            final_results[0].get(
                "cross_encoder_score",
                0.0,
            )
            if final_results
            else 0.0
        )

        reason = "Reranking Failed (Fallback)"

    rerank_time = time.time() - started_at
    end_stage()

    # ------------------------------------------------------------------
    # Final metrics
    # ------------------------------------------------------------------

    _log_pipeline_summary(
        pipeline_start=pipeline_start,
        parse_time=parse_time,
        search_time=search_time,
        fetch_time=fetch_time,
        rerank_time=rerank_time,
        candidate_count=len(candidate_parents),
        final_results=final_results,
        reason=reason,
        top_score=top_score,
    )

    _record_final_retrieval_metrics(
        final_results,
        all_scored_candidates=(reranked if reranked else candidate_parents),
    )
    set_field(
        reranked_candidates=_serialize_parent_candidates(
            reranked if reranked else final_results,
            accepted_ids={str(item.get("parent_id", "")) for item in final_results},
        )
    )

    return RetrievalResult(
        parent_documents=final_results,
        is_empty=not final_results,
    )


# ============================================================================
# Small helpers
# ============================================================================


def _select_reranked_documents(
    reranked: list[dict], settings
) -> tuple[list[dict], str, float]:
    """Apply existing evidence gates and annotate every scored candidate."""
    if not reranked:
        return [], "No documents reranked", 0.0

    top_score = float(reranked[0].get("cross_encoder_score", 0.0))
    minimum_triggered = top_score < settings.rerank_min_top_score
    minimum_score = top_score - settings.rerank_relative_gap
    final_results = (
        []
        if minimum_triggered
        else [
            document
            for document in reranked
            if document.get("cross_encoder_score", 0.0) >= minimum_score
        ][: settings.rerank_top_n]
    )
    accepted_ids = {str(item.get("parent_id", "")) for item in final_results}
    for rank, document in enumerate(reranked, start=1):
        if str(document.get("parent_id", "")) in accepted_ids:
            document["selection_reason"] = "accepted"
        elif minimum_triggered:
            document["selection_reason"] = "minimum_top_score"
        elif document.get("cross_encoder_score", 0.0) < minimum_score:
            document["selection_reason"] = "relative_gap"
        elif rank > settings.rerank_top_n:
            document["selection_reason"] = "outside_top_n"
    reason = (
        "Minimum Evidence Triggered" if minimum_triggered else "Adaptive Relative Gap"
    )
    return final_results, reason, top_score


def _serialize_search_candidates(
    candidates: list[HybridSearchResult],
    matched_queries: dict[str, set[str]] | None = None,
) -> list[dict]:
    """Keep identifiers, rank, score, and provenance for evaluator replay."""
    matched_queries = matched_queries or {}
    return [
        {
            "rank": rank,
            "child_id": candidate.child_id,
            "parent_id": candidate.parent_id,
            "score": round(float(candidate.hybrid_score), 8),
            "score_source": candidate.score_source,
            "title": candidate.document.metadata.get("title", ""),
            "section": candidate.document.metadata.get("section", ""),
            "pages": candidate.document.metadata.get("pages", []),
            "source": candidate.document.metadata.get("source", ""),
            "matched_queries": sorted(matched_queries.get(candidate.child_id, set())),
        }
        for rank, candidate in enumerate(candidates, start=1)
    ]


def _serialize_parent_candidates(
    candidates: list[dict],
    accepted_ids: set[str] | None = None,
) -> list[dict]:
    """Serialize parent candidates without duplicating full document content."""
    return [
        {
            "rank": rank,
            "parent_id": str(candidate.get("parent_id", "")),
            "title": candidate.get("title", ""),
            "section": candidate.get("section", ""),
            "domain": candidate.get("domain", ""),
            "matched_children": candidate.get("matched_children", []),
            "matched_pages": candidate.get("matched_pages", []),
            "search_score": candidate.get("best_child_score"),
            "rerank_score": candidate.get("cross_encoder_score"),
            "score_source": candidate.get("score_source", ""),
            "rerank_method": candidate.get("rerank_method", ""),
            "selection_reason": candidate.get("selection_reason", ""),
            "rerank_original_chars": candidate.get("rerank_original_chars"),
            "rerank_input_chars": candidate.get("rerank_input_chars"),
            "rerank_truncated": candidate.get("rerank_truncated"),
            "rerank_evidence_source": candidate.get("rerank_evidence_source"),
            "rerank_window_start": candidate.get("rerank_window_start"),
            "accepted": (
                str(candidate.get("parent_id", "")) in accepted_ids
                if accepted_ids is not None
                else True
            ),
        }
        for rank, candidate in enumerate(candidates, start=1)
    ]


def _record_detected_domains(
    parsed_queries: list[object],
    detect_panduan_type,
) -> None:
    """Record one domain, MULTI_DOMAIN, or UNKNOWN for planned queries."""
    domains = {
        detect_panduan_type({"source": source})
        for parsed in parsed_queries
        if (source := getattr(parsed, "detected_source", None))
    }
    if len(domains) == 1:
        domain = next(iter(domains))
    elif len(domains) > 1:
        domain = "MULTI_DOMAIN"
    else:
        domain = "UNKNOWN"
    set_field(domain_detected=domain)


def _normalize_search_queries(
    primary_query: str,
    search_queries: tuple[str, ...] | list[str] | None,
) -> tuple[str, ...]:
    """Deduplicate planned queries while preserving their order."""
    candidates = search_queries or (primary_query,)
    normalized: list[str] = []
    for candidate in candidates:
        value = candidate.strip()
        if value and value not in normalized:
            normalized.append(value)
    return tuple(normalized) or (primary_query,)


def _merge_search_results(
    search_batches: list[list[HybridSearchResult]],
) -> list[HybridSearchResult]:
    """Merge child results using cross-query reciprocal-rank fusion."""
    if len(search_batches) <= 1:
        return _deduplicate_single_search(search_batches[0] if search_batches else [])

    best_by_child: dict[str, HybridSearchResult] = {}
    fused_scores: dict[str, float] = {}
    first_seen: list[str] = []
    max_batch_size = max((len(batch) for batch in search_batches), default=0)

    # Round-robin traversal gives equally ranked results from every subquery
    # the same stable priority before parent candidate limiting.
    for rank in range(max_batch_size):
        for batch in search_batches:
            if rank >= len(batch):
                continue
            result = batch[rank]
            child_id = str(getattr(result, "child_id", ""))
            if not child_id:
                continue
            fused_scores[child_id] = fused_scores.get(child_id, 0.0) + 1.0 / (
                MULTI_QUERY_RRF_K + rank + 1
            )
            existing = best_by_child.get(child_id)
            if existing is None:
                first_seen.append(child_id)
            if existing is None or getattr(result, "hybrid_score", 0.0) > getattr(
                existing,
                "hybrid_score",
                0.0,
            ):
                best_by_child[child_id] = result

    for child_id, result in best_by_child.items():
        result.hybrid_score = fused_scores[child_id]
        result.score_source = "multi_query_rrf"

    stable_order = {child_id: index for index, child_id in enumerate(first_seen)}
    return sorted(
        best_by_child.values(),
        key=lambda result: (
            -getattr(result, "hybrid_score", 0.0),
            stable_order[str(getattr(result, "child_id", ""))],
        ),
    )


def _deduplicate_single_search(
    search_results: list[HybridSearchResult],
) -> list[HybridSearchResult]:
    """Preserve the existing score semantics for the common single-query path."""
    best_by_child: dict[str, HybridSearchResult] = {}
    for result in search_results:
        child_id = str(getattr(result, "child_id", ""))
        existing = best_by_child.get(child_id)
        if child_id and (
            existing is None
            or getattr(result, "hybrid_score", 0.0)
            > getattr(existing, "hybrid_score", 0.0)
        ):
            best_by_child[child_id] = result
    return sorted(
        best_by_child.values(),
        key=lambda result: getattr(result, "hybrid_score", 0.0),
        reverse=True,
    )


def _deduplicate_equivalent_child_content(
    search_results: list[HybridSearchResult],
) -> list[HybridSearchResult]:
    """Keep the highest-ranked copy of byte-equivalent knowledge text.

    PI and KKP intentionally share several formatting rules. Returning both
    copies consumes candidate slots without adding evidence when no source was
    selected, so exact normalized duplicates are collapsed after ranking.
    """
    unique: list[HybridSearchResult] = []
    seen_content: set[str] = set()
    duplicate_count = 0
    for result in search_results:
        normalized = " ".join(result.document.page_content.casefold().split())
        if normalized and normalized in seen_content:
            duplicate_count += 1
            continue
        if normalized:
            seen_content.add(normalized)
        unique.append(result)

    if duplicate_count:
        logger.debug(
            "Collapsed {} exact duplicate child candidate(s)",
            duplicate_count,
        )
    return unique


def _skip_reranking(
    candidate_parents: list[dict],
    top_n: int,
) -> list[dict]:
    """
    Skip cross-encoder when candidate count is already small.

    Hybrid score is reused as `cross_encoder_score` so downstream
    consumers can continue using one score field.
    """

    logger.info(
        "Skipping Reranking: only {} candidates",
        len(candidate_parents),
    )

    final_results = [dict(document) for document in candidate_parents[:top_n]]

    for document in final_results:
        document["cross_encoder_score"] = document.get(
            "best_child_score",
            0.0,
        )

        document["score_source"] = "hybrid_skip_rerank"
        document["rerank_method"] = "skipped"

    return final_results


def _log_pipeline_summary(
    *,
    pipeline_start: float,
    parse_time: float,
    search_time: float,
    fetch_time: float,
    rerank_time: float,
    candidate_count: int,
    final_results: list[dict],
    reason: str,
    top_score: float = 0.0,
) -> None:
    """Log retrieval result and stage timings."""

    total_time = time.time() - pipeline_start

    mode = "RAG" if final_results else "Conversation (Empty Context)"

    logger.info(
        "\n"
        "========== Retrieval Summary ==========\n"
        "Retrieved Parents : {}\n"
        "After Threshold   : {}\n"
        "Top Score         : {:.2f}\n"
        "Reason            : {}\n"
        "LLM Mode          : {}\n"
        "=======================================",
        candidate_count,
        len(final_results),
        top_score,
        reason,
        mode,
    )

    logger.info(
        "Retrieval Pipeline | "
        "Total: {:.2f}s | "
        "Parse: {:.2f}s | "
        "Search: {:.2f}s | "
        "Fetch: {:.2f}s | "
        "Rerank: {:.2f}s",
        total_time,
        parse_time,
        search_time,
        fetch_time,
        rerank_time,
    )


# ============================================================================
# Metrics
# ============================================================================


def _record_empty_retrieval_metrics() -> None:
    """Record metrics for an empty retrieval."""

    _record_final_retrieval_metrics(
        [],
        all_scored_candidates=[],
    )


def _record_final_retrieval_metrics(
    final_results: list[dict],
    all_scored_candidates: list[dict] | None = None,
) -> None:
    """
    Record final retrieval metrics.

    Used by both:
        - full reranking
        - adaptive reranking skip
        - empty retrieval
    """

    accepted_ids = {
        document.get(
            "parent_id",
            "",
        )
        for document in final_results
    }

    candidates = (
        all_scored_candidates if all_scored_candidates is not None else final_results
    )

    if not final_results:
        set_field(
            is_no_relevant_doc=True,
            num_docs_after_rerank=0,
            retrieved_parent_ids=[],
            retrieval_detail=_build_retrieval_detail(
                candidates,
                accepted_ids,
            ),
        )
        return

    scores = [
        float(
            document.get(
                "cross_encoder_score",
                0.0,
            )
        )
        for document in final_results
    ]

    set_field(
        is_no_relevant_doc=False,
        num_docs_after_rerank=len(final_results),
        top_cross_encoder_score=(max(scores) if scores else None),
        avg_cross_encoder_score=(sum(scores) / len(scores) if scores else None),
        retrieved_parent_ids=[
            document.get(
                "parent_id",
                "",
            )
            for document in final_results
        ],
        retrieval_detail=_build_retrieval_detail(
            candidates,
            accepted_ids,
        ),
    )


def _build_retrieval_detail(
    candidates: list[dict],
    accepted_ids: set[str],
) -> list[dict]:
    """Build compact retrieval details for JSONB metrics."""

    return [
        {
            "parent_id": candidate.get(
                "parent_id",
                "",
            ),
            "title": (candidate.get("title") or candidate.get("section") or ""),
            "score": round(
                float(
                    candidate.get(
                        "cross_encoder_score",
                        candidate.get(
                            "best_child_score",
                            0.0,
                        ),
                    )
                ),
                4,
            ),
            "score_source": candidate.get(
                "score_source",
                "cross_encoder",
            ),
            "rerank_method": candidate.get(
                "rerank_method",
                "cross_encoder",
            ),
            "search_score_source": candidate.get(
                "search_score_source",
                "rrf",
            ),
            "accepted": (
                candidate.get(
                    "parent_id",
                    "",
                )
                in accepted_ids
            ),
        }
        for candidate in candidates
    ]
