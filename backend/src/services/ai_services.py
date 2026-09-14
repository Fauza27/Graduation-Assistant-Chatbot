"""
AI Services Layer: Orchestrates memory, query rewrite, retrieval, and RAG generation.
"""

from __future__ import annotations

import functools
import time
from typing import Any, Dict, Optional

from loguru import logger

from src.generation.chain import get_rag_generator
from src.generation.intent_classifier.reformulator import (
    needs_rewrite,
    normalize_query,
    reformulate_query,
)
from src.generation.memory import ConversationMemory
from src.generation.summarizer import get_conversation_summarizer
from src.monitoring.context import (
    clear_current,
    end_stage,
    get_current,
    new_collector,
    set_field,
    start_stage,
)
from src.monitoring.errors import classify_exception
from src.monitoring.writer import persist_metrics
from src.services.retrieval_cache import RevisionedRetrievalCache
from src.services.session_strategy import SessionStore, create_session_store, SessionAccessError

retrieval_cache = RevisionedRetrievalCache()

_session_store_strategy: SessionStore = create_session_store()


# ============================================================================
# Cached factory functions for retrieval components
# Menghindari overhead TCP+TLS handshake baru di setiap panggilan run_retrieval().
# Pola ini konsisten dengan @lru_cache yang sudah dipakai di get_llm(),
# get_intent_classifier(), dan _get_default_llm() di modul lain.
# ============================================================================

@functools.lru_cache(maxsize=1)
def _get_hybrid_searcher():
    """Cached singleton HybridSearcher — reuse koneksi Supabase & OpenAI Embeddings."""
    from src.retrieval.hybrid_search import HybridSearcher
    return HybridSearcher()


@functools.lru_cache(maxsize=1)
def _get_parent_child_fetcher():
    """Cached singleton ParentChildFetcher — reuse koneksi Supabase."""
    from src.retrieval.parent_child import ParentChildFetcher
    return ParentChildFetcher()


# ============================================================================
# Session management helpers
# ============================================================================

def get_or_create_memory(
    session_id: str,
    mahasiswa_id: Optional[str] = None,
) -> ConversationMemory:
    """Get or create conversation memory for a session."""
    return _session_store_strategy.load_memory(session_id, mahasiswa_id=mahasiswa_id)


def _save_memory_if_needed(
    session_id: str,
    memory: ConversationMemory,
    channel: str = "telegram",
    mahasiswa_id: Optional[str] = None,
) -> None:
    """Save memory to persistent storage."""
    try:
        _session_store_strategy.save_memory(
            session_id,
            memory,
            channel=channel,
            mahasiswa_id=mahasiswa_id,
        )
    except Exception as exc:
        logger.error("Failed to save session {}: {}", session_id, exc)


def clear_session(session_id: str) -> bool:
    """Clear conversation memory for a session."""
    return _session_store_strategy.delete_session(session_id)


def get_session_stats() -> Dict[str, Any]:
    """Get statistics about active sessions."""
    return _session_store_strategy.get_session_stats()


def cleanup_sessions() -> int:
    """Bersihkan cache session tanpa menghapus data session persisten."""
    return _session_store_strategy.cleanup_cache()


# ============================================================================
# Orchestration step helpers
# ============================================================================

def _resolve_query_and_prepare_memory(
    question: str,
    session_id: str,
    mahasiswa_id: Optional[str],
) -> tuple[str, str, ConversationMemory]:
    """
    Resolve query with memory-aware reformulation if needed,
    and register the user's turn into memory in the proper order.

    Order of operations:
        1. Normalize query
        2. Check if query needs rewrite (implicit references, suffixes, follow-ups)
        3. If rewrite needed:
           - Load memory with PRIOR conversation history
           - Reformulate query using prior context
           - Append current user turn to memory
        4. If rewrite not needed:
           - Load memory
           - Append current user turn to memory
    """
    normalized_query = normalize_query(question)
    rewrite_needed = needs_rewrite(normalized_query)

    start_stage("session_load")
    memory = get_or_create_memory(session_id, mahasiswa_id=mahasiswa_id)
    end_stage()

    resolved_query = normalized_query
    rewrite_method = "None"

    if rewrite_needed and not memory.is_empty:
        start_stage("reformulation")
        t_rewrite_start = time.time()
        # Reformulate using memory prior to adding the current turn
        resolved_query, rewrite_method = reformulate_query(normalized_query, memory)
        t_rewrite_end = time.time()
        end_stage()
        logger.info(
            "[session={}] [Rewrite:{}] '{}' → '{}' [⏱️ {:.2f}s]",
            session_id,
            rewrite_method,
            normalized_query,
            resolved_query,
            t_rewrite_end - t_rewrite_start,
        )

    set_field(rewrite_method=rewrite_method)

    # Register current user turn after reformulation is resolved (gunakan normalized_query
    # agar riwayat percakapan menyimpan istilah akademik terstandardisasi untuk turn berikutnya)
    memory.add_user_turn(normalized_query)

    return resolved_query, rewrite_method, memory


def _get_retrieval_documents(
    resolved_query: str,
    original_question: str,
    collector: Any,
) -> list[dict]:
    """
    Fetch relevant documents with thread-safe caching and monitoring restoration.
    """
    revision, cached_entry = retrieval_cache.lookup(resolved_query, original_question)

    if cached_entry is not None:
        logger.info("⚡ [Cache Hit] Retrieval skipped for: '{}'", resolved_query)
        # Restore monitoring fields so admin dashboard has complete metrics
        set_field(**cached_entry.metrics)
        set_field(cache_hit=True)
        return cached_entry.documents

    logger.info("🔍 [Cache Miss] Running retrieval for: '{}'", resolved_query)
    from src.retrieval.pipeline import run_retrieval

    retrieval = run_retrieval(query=resolved_query, rerank_query=original_question)
    retrieval_docs = (
        retrieval.parent_documents if not retrieval.is_empty else []
    )

    # Snapshot retrieval monitoring fields from collector for future cache hits
    metrics_snapshot = {
        "domain_detected": getattr(collector, "domain_detected", "UNKNOWN"),
        "is_no_relevant_doc": getattr(collector, "is_no_relevant_doc", False),
        "num_docs_after_rerank": getattr(
            collector, "num_docs_after_rerank", len(retrieval_docs)
        ),
        "top_cross_encoder_score": getattr(
            collector, "top_cross_encoder_score", None
        ),
        "avg_cross_encoder_score": getattr(
            collector, "avg_cross_encoder_score", None
        ),
        "retrieved_parent_ids": getattr(
            collector, "retrieved_parent_ids", []
        ),
        "retrieval_detail": getattr(collector, "retrieval_detail", []),
    }

    retrieval_cache.store_if_current(
        revision, resolved_query, original_question, retrieval_docs, metrics_snapshot
    )
    set_field(cache_hit=False)

    return retrieval_docs


def _generate_answer(
    question: str,
    retrieval_docs: list[dict],
    memory: ConversationMemory,
    session_id: str,
) -> str:
    """Generate answer from LLM with retrieved context and conversation history."""
    start_stage("generation")
    t_gen_start = time.time()
    result = get_rag_generator().generate(
        question=question,
        context_documents=retrieval_docs,
        conversation_history=memory.get_history_for_llm(),
        conversation_summary=memory.summary,
    )
    t_gen_end = time.time()
    end_stage()
    logger.info(
        "[session={}] Generation time [⏱️ {:.2f}s]",
        session_id,
        t_gen_end - t_gen_start,
    )
    return result.get("answer", "")


def _compact_memory_if_needed(memory: ConversationMemory) -> None:
    """Pindahkan complete exchanges lama ke summary secara fail-safe."""
    if not memory.needs_compaction:
        return

    turns_to_summarize = memory.get_turns_to_summarize()
    try:
        summary = get_conversation_summarizer().summarize(
            existing_summary=memory.summary,
            turns=turns_to_summarize,
        )
        if not summary:
            logger.warning("Memory summarization menghasilkan teks kosong")
            return

        memory.apply_summary(summary, turns_to_summarize)
        logger.info(
            "Compacted {} old message(s); {} recent turn(s) retained",
            len(turns_to_summarize),
            memory.turn_count,
        )
    except Exception as exc:
        # Jangan membuang turn lama ketika layanan summarization gagal.
        logger.warning("Memory summarization gagal; recent turns dipertahankan: {}", exc)


def _persist_conversation(
    session_id: str,
    memory: ConversationMemory,
    answer: str,
    retrieval_docs: list[dict],
    sources_list: list[dict],
    channel: str,
    mahasiswa_id: Optional[str],
    username: str,
    question: str,
) -> None:
    """Save assistant turn to memory and log interaction."""
    if retrieval_docs:
        memory.add_assistant_turn(
            content=answer,
            retrieved_doc_contents=[
                p.get("content", "") for p in retrieval_docs
            ],
            sources=sources_list,
        )
    else:
        memory.add_assistant_turn(content=answer)

    _compact_memory_if_needed(memory)

    start_stage("db_save")
    _save_memory_if_needed(
        session_id,
        memory,
        channel=channel,
        mahasiswa_id=mahasiswa_id,
    )

    user_id_log = str(mahasiswa_id) if mahasiswa_id else str(session_id)
    _session_store_strategy.log_chat_interaction(
        user_id=user_id_log,
        username=username,
        question=question,
        answer=answer,
    )
    end_stage()


# ============================================================================
# Main chat orchestrator
# ============================================================================

def chat(
    query: str,
    session_id: str,
    username: str,
    channel: str = "telegram",
    mahasiswa_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main chat entrypoint implementing Retrieval-First Architecture.
    """
    if not query or not query.strip():
        return {
            "answer": "Pertanyaan tidak boleh kosong.",
            "num_docs": 0,
            "error": "empty_query",
        }

    if not session_id:
        return {
            "answer": "Session ID diperlukan.",
            "num_docs": 0,
            "error": "missing_session_id",
        }

    collector = get_current()
    if collector is None:
        collector = new_collector(
            session_id=session_id,
            channel=channel,
            mahasiswa_id=mahasiswa_id,
            question=query.strip(),
            username=username,
        )
    else:
        collector.session_id = session_id
        collector.mahasiswa_id = mahasiswa_id
        collector.channel = channel
        collector.question = collector.question or query.strip()
        collector.username = username

    t_start = time.time()
    question = query.strip()
    logger.info("[session={}] Question: {}", session_id, question)

    try:
        # 1 & 2. Query resolution & memory lifecycle preparation
        resolved_query, rewrite_method, memory = _resolve_query_and_prepare_memory(
            question=question,
            session_id=session_id,
            mahasiswa_id=mahasiswa_id,
        )

        # 3. Retrieval with thread-safe caching and monitoring preservation
        retrieval_docs = _get_retrieval_documents(
            resolved_query=resolved_query,
            original_question=question,
            collector=collector,
        )

        # 4. LLM Generation
        answer = _generate_answer(
            question=question,
            retrieval_docs=retrieval_docs,
            memory=memory,
            session_id=session_id,
        )

        # Prepare top sources metadata
        sources_list = (
            [
                {
                    "section": p.get("section", ""),
                    "title": p.get("title", ""),
                    "parent_id": p.get("parent_id", ""),
                    "score": p.get(
                        "cross_encoder_score", p.get("best_child_score", 0.0)
                    ),
                    "score_source": p.get("score_source", "cross_encoder"),
                    "pages": p.get("matched_pages", []),
                }
                for p in retrieval_docs[:3]
            ]
            if retrieval_docs
            else []
        )

        # 5 & 6. Persist conversation state & interaction log
        _persist_conversation(
            session_id=session_id,
            memory=memory,
            answer=answer,
            retrieval_docs=retrieval_docs,
            sources_list=sources_list,
            channel=channel,
            mahasiswa_id=mahasiswa_id,
            username=username,
            question=question,
        )

        t_total_end = time.time()
        logger.info(
            "[session={}] Total process time [⏱️ {:.2f}s]",
            session_id,
            t_total_end - t_start,
        )

        collector.status = "success"
        persist_metrics(collector)

        return {
            "answer": answer,
            "num_docs": len(retrieval_docs),
            "rewrite_method": rewrite_method,
            "sources": sources_list,
        }

    except SessionAccessError:
        # Re-raise SessionAccessError to let global handler convert to HTTP 403
        raise
    except Exception as exc:
        logger.error(
            "[session={}] Error processing query: {}",
            session_id,
            exc,
            exc_info=True,
        )

        error_source, error_type = classify_exception(exc)
        collector.status = "error"
        collector.error_source = error_source
        collector.error_type = error_type
        persist_metrics(collector)

        return {
            "answer": (
                "Maaf, terjadi kesalahan saat memproses pertanyaan Anda. "
                "Silakan coba lagi atau hubungi administrator jika masalah berlanjut."
            ),
            "num_docs": 0,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

    finally:
        # Bersihkan collector dari ContextVar di akhir request supaya tidak
        # "nyangkut" di thread pool yang memakai thread reuse lintas request.
        clear_current()


# ============================================================================
# Model preloading
# ============================================================================

def preload_models() -> None:
    """
    Pre-warm the models used in the RAG pipeline to avoid cold-start delays.
    Memanggil warmup() via cached factory functions supaya instance yang
    di-warm adalah instance yang sama yang dipakai saat runtime.
    """
    logger.info("Pre-warming AI models...")

    t0 = time.time()
    try:
        from src.retrieval.reranker import CrossEncoderReranker

        # 1. Preload Cross-Encoder
        logger.info("Pre-warming: CrossEncoder")
        reranker = CrossEncoderReranker()
        reranker.warmup()

        # 2. Preload Embedding Model — via cached singleton
        logger.info("Pre-warming: Embedding Model")
        _get_hybrid_searcher().warmup()

        # 3. Pastikan ParentChildFetcher juga diinisialisasi sekarang
        # (tidak perlu warmup, tapi cached init menghindari cold-start pertama kali)
        _get_parent_child_fetcher()

        t1 = time.time()
        logger.info("✅ AI models pre-warmed successfully in {:.2f}s", t1 - t0)
    except Exception as exc:
        logger.error("Failed to pre-warm models: {}", exc)
