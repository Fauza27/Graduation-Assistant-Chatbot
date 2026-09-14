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

from loguru import logger

from config.settings import get_settings
from src.monitoring.context import end_stage, set_field, start_stage


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
    if search_queries:
        query = search_queries[0]
    pipeline_start = time.time()

    # ------------------------------------------------------------------
    # Stage 1: Self-query parsing
    # ------------------------------------------------------------------

    start_stage("self_query")
    started_at = time.time()

    try:
        parsed = extract_query_components(query)
    except Exception as exc:
        logger.error(
            "Error in extract_query_components: {}",
            exc,
        )
        parsed = ParsedQuery(
            semantic_query=query,
            filters={},
            original_query=query,
            confidence="low",
        )

    parse_time = time.time() - started_at
    end_stage()

    _record_detected_domain(
        parsed,
        detect_panduan_type,
    )

    # ------------------------------------------------------------------
    # Stage 2: Hybrid search
    # ------------------------------------------------------------------

    started_at = time.time()

    try:
        search_results = _get_hybrid_searcher().search(
            query=parsed.semantic_query,
            filters=parsed.filters,
        )
    except Exception as exc:
        logger.error(
            "Error in HybridSearcher.search: {}",
            exc,
        )
        search_results = []

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

def _record_detected_domain(
    parsed: object,
    detect_panduan_type,
) -> None:
    """Record the domain detected by self-query parsing."""

    detected_source = getattr(
        parsed,
        "detected_source",
        None,
    )

    domain = (
        detect_panduan_type(
            {"source": detected_source}
        )
        if detected_source
        else "UNKNOWN"
    )

    set_field(
        domain_detected=domain
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
