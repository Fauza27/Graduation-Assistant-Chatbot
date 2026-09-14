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

    # ------------------------------------------------------------------
    # Stage 2: Hybrid search
    # ------------------------------------------------------------------

    started_at = time.time()

    search_batches: list[list[HybridSearchResult]] = []
    searcher = _get_hybrid_searcher()

    for parsed in parsed_queries:
        try:
            search_batches.append(
                searcher.search(
                    query=parsed.semantic_query,
                    filters=parsed.filters,
                )
            )
        except Exception as exc:
            logger.error(
                "Error in HybridSearcher.search for '{}': {}",
                parsed.semantic_query,
                exc,
            )

    search_results = _merge_search_results(search_batches)
    set_field(num_docs_retrieved=len(search_results))

    search_time = time.time() - started_at

    if not search_results:
        logger.info(
            "Zero documents found in Hybrid Search. "
            "Short-circuiting."
        )

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
        parent_results = _get_parent_child_fetcher().fetch_parents(
            search_results
        )
    except Exception as exc:
        logger.error(
            "Error in ParentChildFetcher.fetch_parents: {}",
            exc,
        )
        parent_results = []

    fetch_time = time.time() - started_at
    end_stage()

    if not parent_results:
        logger.info(
            "Zero parent documents fetched. "
            "Short-circuiting."
        )

        _record_empty_retrieval_metrics()

        return RetrievalResult(
            parent_documents=[],
            is_empty=True,
        )

    # ------------------------------------------------------------------
    # Stage 4: Limit candidates before reranking
    # ------------------------------------------------------------------

    candidate_parents = parent_results[
        : settings.max_parent_for_rerank
    ]

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
        )

        for document in reranked:
            document["score_source"] = "cross_encoder"
            document["rerank_method"] = "cross_encoder"

        if not reranked:
            reason = "No documents reranked"
        else:
            top_score = float(
                reranked[0].get(
                    "cross_encoder_score",
                    0.0,
                )
            )

            if top_score < settings.rerank_min_top_score:
                final_results = []
                reason = "Minimum Evidence Triggered"
            else:
                min_accepted_score = (
                    top_score
                    - settings.rerank_relative_gap
                )

                final_results = [
                    document
                    for document in reranked
                    if document.get(
                        "cross_encoder_score",
                        0.0,
                    ) >= min_accepted_score
                ][: settings.rerank_top_n]

                reason = "Adaptive Relative Gap"

    except Exception as exc:
        logger.warning(
            "Reranking failed, using unranked top-N: {}",
            exc,
        )

        final_results = [
            dict(document)
            for document in candidate_parents[
                : settings.rerank_top_n
            ]
        ]

        for document in final_results:
            document[
                "cross_encoder_score"
            ] = document.get(
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
        all_scored_candidates=(
            reranked
            if reranked
            else candidate_parents
        ),
    )

    return RetrievalResult(
        parent_documents=final_results,
        is_empty=not final_results,
    )


# ============================================================================
# Small helpers
# ============================================================================

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

    final_results = [
        dict(document)
        for document in candidate_parents[:top_n]
    ]

    for document in final_results:
        document[
            "cross_encoder_score"
        ] = document.get(
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

    mode = (
        "RAG"
        if final_results
        else "Conversation (Empty Context)"
    )

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
        all_scored_candidates
        if all_scored_candidates is not None
        else final_results
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
        top_cross_encoder_score=(
            max(scores)
            if scores
            else None
        ),
        avg_cross_encoder_score=(
            sum(scores) / len(scores)
            if scores
            else None
        ),
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
            "title": (
                candidate.get("title")
                or candidate.get("section")
                or ""
            ),
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
