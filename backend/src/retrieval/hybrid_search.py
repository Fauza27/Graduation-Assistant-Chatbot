"""Hybrid BM25 + vector search."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import tiktoken
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from loguru import logger
from supabase import Client, create_client

from config.settings import get_settings
from src.monitoring.context import end_stage, set_field, start_stage
from src.monitoring.pricing import calculate_embedding_cost
from src.monitoring.errors import RetrievalError
from src.monitoring.openai_client import (
    build_instrumented_http_client,
)
from src.retrieval.query_expansion import expand_query_smart
from src.security.content_safety import text_for_log


settings = get_settings()

EMBEDDING_DIMENSIONS = 2000
RRF_K_DEFAULT = 60
DENSE_FALLBACK_THRESHOLD = getattr(
    settings,
    "dense_fallback_threshold",
    0.3,
)


@dataclass
class HybridSearchResult:
    """Normalized result from hybrid or dense search."""

    document: Document
    hybrid_score: float
    child_id: str
    parent_id: str
    score_source: str = field(
        default="rrf"
    )


class HybridSearcher:
    """
    Hybrid retriever using PostgreSQL BM25/FTS + vector search.

    Query expansion is applied only to FTS/BM25.
    Vector search always uses the original query.
    """

    def __init__(
        self,
        supabase_client: Client | None = None,
    ) -> None:
        self._supabase = (
            supabase_client
            or create_client(
                settings.supabase_url,
                settings.supabase_service_key,
            )
        )

        self._embedder = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.open_api_key,
            dimensions=EMBEDDING_DIMENSIONS,
            http_client=build_instrumented_http_client(),
        )

    def warmup(self) -> None:
        """Pre-warm the embedding model and underlying HTTP connection."""
        self._embedder.embed_query("warmup")

    def search(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        top_k: int | None = None,
        enable_query_expansion: bool = True,
    ) -> list[HybridSearchResult]:
        """Run hybrid search and return normalized results."""

        filters = filters or {}
        match_count = (
            top_k
            if top_k is not None
            else settings.retrieval_top_k
        )

        original_query = query

        expanded_query = (
            expand_query_smart(query)
            if enable_query_expansion
            else query
        )

        if expanded_query != original_query:
            logger.info(
                "Query expansion applied: "
                "'{}' → '{}'",
                text_for_log(original_query),
                text_for_log(expanded_query, preview_length=150),
            )

        logger.info(
            "Hybrid search: '{}' | filters={} | top_k={}",
            text_for_log(original_query),
            filters,
            match_count,
        )

        query_embedding = self._create_embedding(
            original_query
        )

        if query_embedding is None:
            logger.warning(
                "Query embedding gagal dihitung untuk '{}'. "
                "Menjalankan fallback pencarian Full-Text Search (FTS) murni.",
                original_query,
            )
            rows = self._fts_fallback(
                expanded_query=expanded_query,
                filters=filters,
                match_count=match_count,
            )
            score_source = "fts_only_fallback"
        else:
            rows, score_source = self._execute_search(
                original_query=original_query,
                expanded_query=expanded_query,
                query_embedding=query_embedding,
                filters=filters,
                match_count=match_count,
            )

        results = self._build_results(
            rows=rows,
            score_source=score_source,
        )

        logger.info(
            "Hybrid search selesai: "
            "{} results (source={})",
            len(results),
            score_source,
        )

        if results:
            logger.info(
                "Top: {} | score={:.4f}",
                results[0].child_id,
                results[0].hybrid_score,
            )

        set_field(
            num_docs_retrieved=len(results)
        )

        return results

    def _create_embedding(
        self,
        query: str,
    ) -> list[float] | None:
        """Create query embedding and record usage."""

        start_stage("embedding")
        started_at = time.time()

        try:
            embedding = self._embedder.embed_query(
                query
            )
        except Exception as exc:
            logger.error(
                "Gagal menghitung embedding: {}",
                exc,
            )
            end_stage()
            return None

        elapsed = time.time() - started_at
        end_stage()

        logger.info(
            "[Profile] Query Embedding: {:.2f}s",
            elapsed,
        )

        try:
            encoder = tiktoken.encoding_for_model(
                settings.embedding_model
            )
        except Exception:
            encoder = tiktoken.get_encoding(
                "cl100k_base"
            )

        token_count = len(
            encoder.encode(query)
        )

        cost = calculate_embedding_cost(
            settings.embedding_model,
            token_count,
        )

        set_field(
            embedding_tokens=token_count,
            embedding_cost_usd=cost,
        )

        return embedding

    def _execute_search(
        self,
        original_query: str,
        expanded_query: str,
        query_embedding: list[float],
        filters: dict[str, str],
        match_count: int,
    ) -> tuple[list[dict[str, Any]], str]:
        """Run hybrid search and dense fallback."""

        rpc_params: dict[str, Any] = {
            "query_embedding": query_embedding,
            "query_text": expanded_query,
            "match_count": match_count,
            "fts_weight": settings.bm25_weight,
            "vector_weight": settings.dense_weight,
            "rrf_k": RRF_K_DEFAULT,
            "filter_section": filters.get(
                "section"
            ),
            "filter_source": filters.get(
                "source"
            ),
        }

        start_stage("retrieval")
        started_at = time.time()

        hybrid_error: Exception | None = None
        try:
            response = self._supabase.rpc(
                "hybrid_search",
                rpc_params,
            ).execute()

            rows = response.data or []

        except Exception as exc:
            logger.error(
                "Hybrid search RPC gagal: {}",
                exc,
            )
            hybrid_error = exc
            rows = []

        elapsed = time.time() - started_at
        end_stage()

        logger.info(
            "[Profile] Supabase Hybrid RPC: {:.2f}s",
            elapsed,
        )

        if rows:
            return rows, "rrf"

        logger.warning(
            "Tidak ada hasil hybrid_search RPC."
        )

        try:
            fallback_rows = self._dense_fallback(
                query_embedding=query_embedding,
                filters=filters,
                match_count=match_count,
            )
        except RetrievalError as exc:
            if hybrid_error is not None:
                raise RetrievalError(
                    "Hybrid dan dense search database RPC gagal"
                ) from exc
            raise

        if not fallback_rows:
            return [], "dense_fallback"

        return fallback_rows, "dense_fallback"

    def _dense_fallback(
        self,
        query_embedding: list[float],
        filters: dict[str, str],
        match_count: int,
    ) -> list[dict[str, Any]]:
        """Run dense-only search when hybrid returns nothing."""

        logger.info(
            "Fallback ke dense-only via "
            "match_child_documents..."
        )

        try:
            response = self._supabase.rpc(
                "match_child_documents",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": DENSE_FALLBACK_THRESHOLD,
                    "match_count": match_count,
                    "filter_section": filters.get(
                        "section"
                    ),
                    "filter_source": filters.get(
                        "source"
                    ),
                },
            ).execute()

        except Exception as exc:
            logger.error(
                "Fallback dense search RPC gagal: {}",
                exc,
            )
            raise RetrievalError("Dense fallback database RPC gagal") from exc

        if not response.data:
            logger.warning(
                "Dense search juga kosong."
            )
            return []

        normalized_rows: list[dict[str, Any]] = []

        for row in response.data:
            normalized = dict(row)

            normalized["rrf_score"] = normalized.get(
                "similarity",
                0.0,
            )

            normalized_rows.append(
                normalized
            )

        return normalized_rows

    def _fts_fallback(
        self,
        expanded_query: str,
        filters: dict[str, str],
        match_count: int,
    ) -> list[dict[str, Any]]:
        """Run pure Full-Text Search fallback via search_fts_child_documents RPC."""
        logger.info(
            "Fallback ke FTS-only via search_fts_child_documents..."
        )

        start_stage("retrieval")
        started_at = time.time()

        try:
            response = self._supabase.rpc(
                "search_fts_child_documents",
                {
                    "query_text": expanded_query,
                    "match_count": match_count,
                    "filter_section": filters.get("section"),
                    "filter_source": filters.get("source"),
                },
            ).execute()
        except Exception as exc:
            logger.error(
                "Fallback FTS search RPC gagal: {}",
                exc,
            )
            end_stage()
            raise RetrievalError("FTS fallback database RPC gagal") from exc

        elapsed = time.time() - started_at
        end_stage()

        logger.info(
            "[Profile] Supabase FTS Fallback RPC: {:.2f}s",
            elapsed,
        )

        if not response.data:
            logger.warning(
                "FTS search fallback tidak menghasilkan dokumen."
            )
            return []

        normalized_rows: list[dict[str, Any]] = []
        for row in response.data:
            normalized = dict(row)
            # Normalisasi fts_rank ke rrf_score agar seragam dengan output RRF
            normalized["rrf_score"] = normalized.get(
                "fts_rank",
                0.0,
            )
            normalized_rows.append(normalized)

        return normalized_rows

    @staticmethod
    def _build_results(
        rows: list[dict[str, Any]],
        score_source: str,
    ) -> list[HybridSearchResult]:
        """Convert database rows into typed search results."""

        results: list[HybridSearchResult] = []

        for row in rows:
            document = Document(
                page_content=row.get(
                    "content",
                    "",
                ),
                metadata={
                    "child_id": row.get(
                        "id",
                        "",
                    ),
                    "parent_id": row.get(
                        "parent_id",
                        "",
                    ),
                    "title": row.get(
                        "title",
                        "",
                    ),
                    "section": row.get(
                        "section",
                        "",
                    ),
                    "pages": row.get(
                        "pages",
                        [],
                    ),
                    "source": row.get(
                        "source",
                        "",
                    ),
                },
            )

            results.append(
                HybridSearchResult(
                    document=document,
                    hybrid_score=float(
                        row.get(
                            "rrf_score",
                            0.0,
                        )
                    ),
                    child_id=row.get(
                        "id",
                        "",
                    ),
                    parent_id=row.get(
                        "parent_id",
                        "",
                    ),
                    score_source=score_source,
                )
            )

        return results
