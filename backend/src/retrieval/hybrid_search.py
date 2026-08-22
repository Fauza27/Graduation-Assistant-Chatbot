from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import time
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from loguru import logger
from supabase import Client, create_client

from config.settings import get_settings
from src.retrieval.query_expansion import expand_query_smart

settings = get_settings()

EMBEDDING_DIMENSIONS = 2000
RRF_K_DEFAULT = 60


@dataclass
class HybridSearchResult:
    """
    Hasil pencarian hybrid (BM25 FTS + vector) yang sudah digabung lewat RRF
    di sisi PostgreSQL. Lihat fungsi `hybrid_search` di scripts/supabase.sql.
    """
    document: Document
    hybrid_score: float
    child_id: str
    parent_id: str


class HybridSearcher:
    """
    Hybrid retriever yang melakukan fusion BM25 + vector di PostgreSQL.

    Tokenisasi BM25 menggunakan `to_tsvector('indonesian')` di Postgres
    (memiliki Snowball stemmer untuk bahasa Indonesia). Bobot fusion dan
    parameter RRF dikontrol via settings.
    """

    def __init__(self, supabase_client: Client | None = None):
        self._supabase = supabase_client or create_client(
            settings.supabase_url, settings.supabase_service_key
        )
        from src.monitoring.openai_client import build_instrumented_http_client
        self._embedder = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.open_api_key,
            dimensions=EMBEDDING_DIMENSIONS,
            http_client=build_instrumented_http_client(),
        )

    def search(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        top_k: int | None = None,
        enable_query_expansion: bool = True,
    ) -> list[HybridSearchResult]:
        """
        Melakukan pencarian hybrid (BM25 + Vector) di database Supabase.
        
        Args:
            query: Teks pencarian dari pengguna
            filters: Dictionary filter metadata (seperti section)
            top_k: Jumlah hasil maksimal yang dikembalikan
            enable_query_expansion: Flag untuk mengekspansi query (default: True)
            
        Returns:
            List dari HybridSearchResult yang berisi dokumen dan skor RRF.
        """
        k = top_k or settings.retrieval_top_k
        filters = filters or {}

        # Apply query expansion for better recall.
        original_query = query
        if enable_query_expansion:
            query = expand_query_smart(query, enable_expansion=True)
            if query != original_query:
                logger.info(
                    f"Query expansion applied: '{original_query}' → '{query[:100]}...'"
                )

        logger.info(f"Hybrid search: '{original_query}' | filters: {filters} | top_k: {k}")

        from src.monitoring.context import start_stage, end_stage

        start_stage("embedding")
        t0 = time.time()
        query_embedding = self._embedder.embed_query(query)
        t_embed = time.time() - t0
        end_stage()
        logger.info(f"  [Profile] Query Embedding: {t_embed:.2f}s")

        import tiktoken
        from src.monitoring.pricing import calculate_embedding_cost

        try:
            _enc = tiktoken.encoding_for_model("text-embedding-3-large")
        except Exception:
            _enc = tiktoken.get_encoding("cl100k_base")
        embed_tokens = len(_enc.encode(query))
        embed_cost = calculate_embedding_cost(settings.embedding_model, embed_tokens)
        from src.monitoring.context import set_field
        set_field(embedding_tokens=embed_tokens, embedding_cost_usd=embed_cost)

        rpc_params: dict[str, Any] = {
            "query_embedding": query_embedding,
            "query_text": query,
            "match_count": k,
            "fts_weight": settings.bm25_weight,
            "vector_weight": settings.dense_weight,
            "rrf_k": RRF_K_DEFAULT,
            "filter_section": filters.get("section"),
            "filter_source": filters.get("source"),
        }

        start_stage("retrieval")
        t1 = time.time()
        response = self._supabase.rpc("hybrid_search", rpc_params).execute()
        t_rpc = time.time() - t1
        end_stage()
        logger.info(f"  [Profile] Supabase Hybrid RPC: {t_rpc:.2f}s")
        
        db_results = response.data or []

        # Fallback: kalau hybrid search tidak menemukan apa pun (mis. query
        # tidak match FTS sama sekali dan vector juga lemah), coba dense-only.
        if not db_results:
            logger.warning("Tidak ada hasil dari hybrid_search RPC.")
            logger.info("Fallback ke dense-only via match_child_documents...")
            fallback_response = self._supabase.rpc(
                "match_child_documents",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": 0.0,
                    "match_count": k,
                    "filter_section": filters.get("section"),
                    "filter_source": filters.get("source"),
                },
            ).execute()

            if not fallback_response.data:
                logger.warning("Dense search juga kosong, tidak ada hasil.")
                return []

            # Normalisasi field: dense-only return `similarity`, kita pakai
            # itu sebagai hybrid_score agar struktur output konsisten.
            db_results = []
            for row in fallback_response.data:
                row = dict(row)
                row["rrf_score"] = row.get("similarity", 0.0)
                db_results.append(row)

        results: list[HybridSearchResult] = []
        for row in db_results:
            doc = Document(
                page_content=row["content"],
                metadata={
                    "child_id": row["id"],
                    "parent_id": row.get("parent_id", ""),
                    "title": row.get("title", ""),
                    "section": row.get("section", ""),
                    "pages": row.get("pages", []),
                    "source": row.get("source", ""),
                },
            )

            results.append(
                HybridSearchResult(
                    document=doc,
                    hybrid_score=float(row.get("rrf_score", 0.0)),
                    child_id=row["id"],
                    parent_id=row.get("parent_id", ""),
                )
            )

        logger.info(f"Hybrid search selesai: {len(results)} results")
        if results:
            logger.info(
                f"  Top: {results[0].child_id} | hybrid={results[0].hybrid_score:.4f}"
            )

        from src.monitoring.context import set_field
        set_field(num_docs_retrieved=len(results))
        return results
