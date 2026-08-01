"""
Single source of truth untuk pipeline retrieval RAG:
self-query → hybrid search → parent fetching → reranking.

Fungsi `run_retrieval` dipakai oleh:
- `src/services/ai_services.py`

Mengimplementasikan:
- Candidate Limiting (membatasi parent yang direrank)
- Adaptive Reranking (skip rerank jika dokumen <= batas minimal)
- Zero-doc shortcircuit
"""

from __future__ import annotations

from dataclasses import dataclass
import time

from loguru import logger

from config.settings import get_settings


@dataclass
class RetrievalResult:
    """Hasil pipeline retrieval, siap dikonsumsi generator."""
    parent_documents: list[dict]
    is_empty: bool

    @property
    def num_docs(self) -> int:
        return len(self.parent_documents)


def run_retrieval(query: str, rerank_query: str | None = None) -> RetrievalResult:
    """
    Jalankan pipeline retrieval lengkap untuk satu query.

    `query` adalah teks yang dipakai untuk semantic search (sudah
    direformulasi kalau perlu).
    `rerank_query` adalah teks yang dipakai cross-encoder; default ke
    `query` kalau tidak diberikan. Biasanya pakai pertanyaan asli user
    di sini agar reranking konsisten dengan intent original.
    """
    from src.retrieval.self_query import extract_query_components
    from src.retrieval.hybrid_search import HybridSearcher
    from src.retrieval.parent_child import ParentChildFetcher
    from src.retrieval.reranker import CrossEncoderReranker

    settings = get_settings()
    rerank_query = rerank_query or query

    t_start = time.time()
    parsed = extract_query_components(query)
    t_parse = time.time()

    searcher = HybridSearcher()
    search_results = searcher.search(
        query=parsed.semantic_query,
        filters=parsed.filters,
    )
    t_search = time.time()

    if not search_results:
        logger.info("⏭️ Zero documents found in Hybrid Search. Short-circuiting.")
        return RetrievalResult(parent_documents=[], is_empty=True)

    fetcher = ParentChildFetcher()
    parent_results = fetcher.fetch_parents(search_results)
    t_fetch = time.time()

    if not parent_results:
        logger.info("⏭️ Zero parent documents fetched. Short-circuiting.")
        return RetrievalResult(parent_documents=[], is_empty=True)

    # Candidate Limiting: Ambil Top N parent sebelum di-rerank
    # (fetch_parents sudah mensortir secara descending berdasarkan hybrid score)
    candidate_parents = parent_results[: settings.max_parent_for_rerank]
    
    # Adaptive Reranking: Skip Reranking jika kandidat sedikit
    if len(candidate_parents) <= settings.min_parent_for_rerank:
        logger.info(f"⏭️ Skipping Reranking: only {len(candidate_parents)} candidates (<= {settings.min_parent_for_rerank})")
        
        final_results = candidate_parents[: settings.rerank_top_n]
        # Pastikan ada key cross_encoder_score agar format seragam
        for p in final_results:
            p["cross_encoder_score"] = p.get("best_child_score", 0.0)
            
        t_rerank = time.time()
        logger.info(f"⏱️ [Retrieval Pipeline] Total: {t_rerank - t_start:.2f}s | "
                    f"Parse: {t_parse - t_start:.2f}s | "
                    f"Search: {t_search - t_parse:.2f}s | "
                    f"Fetch: {t_fetch - t_search:.2f}s | "
                    f"Rerank (Skipped): 0.00s")
        return RetrievalResult(parent_documents=final_results, is_empty=False)

    try:
        reranker = CrossEncoderReranker()
        reranked = reranker.rerank(query=rerank_query, documents=candidate_parents)
        
        if reranked:
            top_score = reranked[0].get("cross_encoder_score", 0.0)
            
            if top_score < settings.rerank_min_top_score:
                final_results = []
                reason = "Minimum Evidence Triggered"
            else:
                min_accepted_score = top_score - settings.rerank_relative_gap
                final_results = [
                    doc for doc in reranked 
                    if doc.get("cross_encoder_score", 0.0) >= min_accepted_score
                ][: settings.rerank_top_n]
                reason = "Adaptive Relative Gap"
        else:
            final_results = []
            reason = "No documents reranked"
            top_score = 0.0
            
    except Exception as e:
        logger.warning(f"Reranking failed, using unranked top-N: {e}")
        final_results = candidate_parents[: settings.rerank_top_n]
        reason = "Reranking Failed (Fallback)"
        top_score = final_results[0].get("best_child_score", 0.0) if final_results else 0.0
        
    t_rerank = time.time()
    
    summary_log = (
        f"\n========== Retrieval Summary ==========\n"
        f"Retrieved Parents : {len(candidate_parents)}\n"
        f"After Threshold   : {len(final_results)}\n"
        f"Top Score         : {top_score:.2f}\n"
        f"Reason            : {reason}\n"
        f"LLM Mode          : {'Conversation (Empty Context)' if not final_results else 'RAG'}\n"
        f"======================================="
    )
    logger.info(summary_log)
    
    logger.info(f"⏱️ [Retrieval Pipeline] Total: {t_rerank - t_start:.2f}s | "
                f"Parse: {t_parse - t_start:.2f}s | "
                f"Search: {t_search - t_parse:.2f}s | "
                f"Fetch: {t_fetch - t_search:.2f}s | "
                f"Rerank: {t_rerank - t_fetch:.2f}s")

    return RetrievalResult(parent_documents=final_results, is_empty=(len(final_results) == 0))
