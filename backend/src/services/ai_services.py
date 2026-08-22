from typing import Dict, Any, Optional
import time
from loguru import logger
from cachetools import TTLCache

from src.generation.memory import ConversationMemory
from src.generation.intent_classifier.reformulator import normalize_query, needs_rewrite, reformulate_query
from src.generation.chain import RAGChain
from src.services.session_strategy import create_session_store, SessionStore
from src.monitoring.context import new_collector, start_stage, end_stage, set_field, get_current
from src.monitoring.writer import persist_metrics
from src.monitoring.errors import ChatError, RetrievalError, classify_exception
from config.settings import get_settings

settings = get_settings()

# Cache for retrieval results (max 500 items, TTL 30 minutes)
retrieval_cache = TTLCache(maxsize=500, ttl=1800)
KNOWLEDGE_VERSION = "v1"

# Initialize session store strategy (dipilih sekali saat startup)
_session_store_strategy: SessionStore = create_session_store()

_rag_chain = RAGChain()

# NOTE: ChatError & RetrievalError sekarang didefinisikan di
# src/monitoring/errors.py (diimpor di atas) supaya taksonomi error
# konsisten dipakai di seluruh codebase, termasuk untuk klasifikasi
# `error_source` di request_metrics.


def get_or_create_memory(session_id: str, mahasiswa_id: Optional[str] = None) -> ConversationMemory:
    """Get or create conversation memory for a session."""
    return _session_store_strategy.load_memory(session_id, mahasiswa_id=mahasiswa_id)


def _save_memory_if_needed(session_id: str, memory: ConversationMemory, channel: str = "telegram", mahasiswa_id: Optional[str] = None) -> None:
    """Save memory to persistent storage."""
    try:
        _session_store_strategy.save_memory(session_id, memory, channel=channel, mahasiswa_id=mahasiswa_id)
    except Exception as e:
        logger.error(f"Failed to save session {session_id}: {e}")


def clear_session(session_id: str) -> bool:
    """Clear conversation memory for a session"""
    return _session_store_strategy.delete_session(session_id)


def get_session_stats() -> Dict[str, Any]:
    """Get statistics about active sessions"""
    return _session_store_strategy.get_session_stats()


def cleanup_sessions() -> int:
    """Manually trigger session cleanup. Returns number of sessions cleaned."""
    return _session_store_strategy.cleanup_idle_sessions()


def chat(query: str, session_id: str, username: str, channel: str = "telegram", mahasiswa_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Main chat function implementing Retrieval-First Architecture.
    """
    if not query or not query.strip():
        return {"answer": "Pertanyaan tidak boleh kosong.", "num_docs": 0, "error": "empty_query"}

    if not session_id:
        return {"answer": "Session ID diperlukan.", "num_docs": 0, "error": "missing_session_id"}

    # Kalau titik masuk (ai.py / chat_handler.py, Fase 5) SUDAH membuat
    # collector duluan untuk mengukur tahap "validation", pakai itu.
    # Kalau belum ada (mis. dipanggil langsung dari script/test), buat baru
    # di sini supaya fungsi ini tetap bisa dipakai standalone.
    collector = get_current()
    if collector is None:
        collector = new_collector(
            session_id=session_id, channel=channel, mahasiswa_id=mahasiswa_id,
            question=query.strip(), username=username,
        )
    else:
        collector.session_id = session_id
        collector.mahasiswa_id = mahasiswa_id
        collector.channel = channel
        # G1/G3/G4/G6: pastikan question/username terisi walau collector-nya
        # sudah dibuat lebih dulu di Fase 5 (ai.py/chat_handler.py) — di sana
        # `username` final (hasil resolve JWT/profil Telegram) baru diketahui
        # SETELAH collector dibuat, jadi di-set (ulang) di sini untuk jaga-jaga.
        collector.question = collector.question or query.strip()
        collector.username = username

    t_start = time.time()
    question = query.strip()
    logger.info(f"[session={session_id}] Question: {question}")

    try:
        # 1. Normalization
        normalized_query = normalize_query(question)

        # 2. Need Rewrite?
        rewrite_needed = needs_rewrite(normalized_query)

        resolved_query = normalized_query
        rewrite_method = "None"
        memory = None

        # SLOW PATH: Load memory early for query rewrite
        if rewrite_needed:
            start_stage("session_load")
            memory = get_or_create_memory(session_id, mahasiswa_id=mahasiswa_id)
            end_stage()
            memory.add_user_turn(question)

            start_stage("reformulation")
            t_rewrite_start = time.time()
            resolved_query, rewrite_method = reformulate_query(normalized_query, memory)
            t_rewrite_end = time.time()
            end_stage()
            logger.info(f"[session={session_id}] [Rewrite] {rewrite_method}: '{normalized_query}' → '{resolved_query}' [⏱️ {t_rewrite_end - t_rewrite_start:.2f}s]")

        set_field(rewrite_method=rewrite_method)

        # 3. Cache Check
        cache_key = f"{KNOWLEDGE_VERSION}_{resolved_query}"
        cached_result = retrieval_cache.get(cache_key)

        if cached_result is not None:
            logger.info(f"⚡ [Cache Hit] Retrieval skipped for: '{resolved_query}'")
            retrieval_docs = cached_result
        else:
            logger.info(f"🔍 [Cache Miss] Running retrieval for: '{resolved_query}'")
            from src.retrieval.pipeline import run_retrieval
            retrieval = run_retrieval(query=resolved_query, rerank_query=question)
            retrieval_docs = retrieval.parent_documents
            # Cache the results
            retrieval_cache[cache_key] = retrieval_docs
            # NOTE: retrieval.* field tambahan (domain_detected, skor, dst)
            # sudah otomatis ditulis ke collector oleh run_retrieval() itu
            # sendiri di Fase 3 — tidak perlu diulang manual di sini.
            # Kalau cache HIT, field-field itu TIDAK terisi untuk request
            # ini (retrieval tidak benar-benar jalan) — ini trade-off yang
            # disengaja, cache hit memang tidak merepresentasikan retrieval
            # baru.

        # FAST PATH: Load memory here if not loaded yet
        if memory is None:
            start_stage("session_load")
            memory = get_or_create_memory(session_id, mahasiswa_id=mahasiswa_id)
            end_stage()
            memory.add_user_turn(question)

        # 4. LLM Generation
        start_stage("generation")
        t_gen_start = time.time()
        result = _rag_chain.invoke_with_history(
            question=question,
            context_documents=retrieval_docs,
            conversation_history=memory.get_history_for_llm(),
        )
        t_gen_end = time.time()
        end_stage()
        logger.info(f"[session={session_id}] Generation time [⏱️ {t_gen_end - t_gen_start:.2f}s]")

        answer = result["answer"]

        # Prepare sources metadata
        sources_list = [
            {
                "section": p.get("section", ""),
                "title": p.get("title", ""),
                "parent_id": p.get("parent_id", ""),
                "score": p.get("cross_encoder_score", 0.0),
                "pages": p.get("matched_pages", []),
            }
            for p in retrieval_docs[:3]
        ] if retrieval_docs else []

        # 5. Save state
        if retrieval_docs:
            memory.add_assistant_turn(
                content=answer,
                retrieved_doc_contents=[p["content"] for p in retrieval_docs],
                sources=sources_list,
            )
        else:
            memory.add_assistant_turn(content=answer)

        start_stage("db_save")
        _save_memory_if_needed(session_id, memory, channel=channel, mahasiswa_id=mahasiswa_id)

        t_total_end = time.time()
        logger.info(f"[session={session_id}] Total process time [⏱️ {t_total_end - t_start:.2f}s]")

        # 6. Catat chat log (chat_logs, tabel lama — TIDAK diubah)
        try:
            # Use strategy untuk get database access jika menggunakan database sessions
            if hasattr(_session_store_strategy, '_store') and hasattr(_session_store_strategy._store, '_supabase'):
                user_id_log = str(mahasiswa_id) if mahasiswa_id else str(session_id)
                _session_store_strategy._store._supabase.table("chat_logs").insert({
                    "user_id": user_id_log,
                    "username": username,
                    "question": question,
                    "answer": answer,
                }).execute()
        except Exception as e:
            user_id_log = str(mahasiswa_id) if mahasiswa_id else str(session_id)
            logger.error(f"Gagal menyimpan log chat untuk user {user_id_log}: {e}")
        end_stage()  # menutup db_save

        collector.status = "success"
        persist_metrics(collector)

        return {
            "answer": answer,
            "num_docs": len(retrieval_docs),
            "rewrite_method": rewrite_method,
            "sources": sources_list,
        }

    except Exception as e:
        logger.error(f"[session={session_id}] Error processing query: {e}", exc_info=True)

        error_source, error_type = classify_exception(e)
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
            "error": str(e),
            "error_type": type(e).__name__,
        }

def preload_models() -> None:
    """
    Pre-warm the models used in the RAG pipeline to avoid cold-start delays.
    This includes loading the embedding model (and its dependencies like tiktoken)
    and the cross-encoder model (which loads PyTorch and the weights).
    """
    logger.info("Pre-warming AI models...")
    
    t0 = time.time()
    try:
        from src.retrieval.hybrid_search import HybridSearcher
        from src.retrieval.reranker import CrossEncoderReranker
        
        # 1. Preload Cross-Encoder
        logger.info("Pre-warming: CrossEncoder")
        reranker = CrossEncoderReranker()
        reranker._get_model()  # Forces model to load into memory
        
        # 2. Preload Embedding Model (OpenAI API / tiktoken)
        logger.info("Pre-warming: Embedding Model")
        searcher = HybridSearcher()
        searcher._embedder.embed_query("warmup")
        
        t1 = time.time()
        logger.info(f"✅ AI models pre-warmed successfully in {t1 - t0:.2f}s")
    except Exception as e:
        logger.error(f"Failed to pre-warm models: {e}")
