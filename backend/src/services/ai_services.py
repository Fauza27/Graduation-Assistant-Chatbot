from typing import Dict, Any, Optional
import time
from loguru import logger
from cachetools import TTLCache

from src.generation.memory import ConversationMemory
from src.generation.intent_classifier.reformulator import normalize_query, needs_rewrite, reformulate_query
from src.generation.chain import RAGChain
from src.services.session_store import get_session_store
from config.settings import get_settings

settings = get_settings()

# Cache for retrieval results (max 500 items, TTL 30 minutes)
retrieval_cache = TTLCache(maxsize=500, ttl=1800)
KNOWLEDGE_VERSION = "v1"

# Legacy in-memory session store (fallback jika database tidak tersedia)
_legacy_session_store: dict[str, tuple[ConversationMemory, float]] = {}
_legacy_session_lock = None

# Initialize session store berdasarkan konfigurasi
if settings.USE_DATABASE_SESSIONS:
    try:
        _session_store = get_session_store()
        logger.info("Using database-backed session storage")
    except Exception as e:
        logger.error(f"Failed to initialize database session store: {e}")
        logger.warning("Falling back to in-memory session storage")
        settings.USE_DATABASE_SESSIONS = False

if not settings.USE_DATABASE_SESSIONS:
    from threading import Lock
    _legacy_session_lock = Lock()
    logger.info("Using in-memory session storage")

_rag_chain = RAGChain()


class ChatError(Exception):
    """Custom exception for chat-related errors"""
    pass


class RetrievalError(ChatError):
    """Exception for retrieval-related errors"""
    pass


def _evict_idle_sessions(now: float) -> int:
    """Hapus session yang idle melebihi SESSION_CLEANUP_INTERVAL detik (legacy in-memory only)."""
    if settings.USE_DATABASE_SESSIONS:
        return 0  # Database handles cleanup
    
    ttl = settings.SESSION_CLEANUP_INTERVAL
    expired = [sid for sid, (_, last_ts) in _legacy_session_store.items() if now - last_ts > ttl]
    for sid in expired:
        _legacy_session_store.pop(sid, None)
    if expired:
        logger.info(f"Evicted {len(expired)} idle session(s)")
    return len(expired)


def _evict_lru_if_full() -> None:
    """Jika store sudah penuh, hapus session paling lama tidak diakses (legacy in-memory only)."""
    if settings.USE_DATABASE_SESSIONS:
        return  # Database handles LRU
    
    cap = settings.MAX_ACTIVE_SESSIONS
    if len(_legacy_session_store) <= cap:
        return
    # Sort by last_access_ts ascending; buang sampai cap.
    overflow = len(_legacy_session_store) - cap
    sorted_items = sorted(_legacy_session_store.items(), key=lambda kv: kv[1][1])
    for sid, _ in sorted_items[:overflow]:
        _legacy_session_store.pop(sid, None)
    logger.info(f"Evicted {overflow} LRU session(s) due to MAX_ACTIVE_SESSIONS cap")


def get_or_create_memory(session_id: str) -> ConversationMemory:
    """Get or create conversation memory for a session."""
    if settings.USE_DATABASE_SESSIONS:
        return _session_store.load_memory(session_id)
    
    # Legacy in-memory session storage
    now = time.time()
    with _legacy_session_lock:
        _evict_idle_sessions(now)

        existing = _legacy_session_store.get(session_id)
        if existing is not None:
            memory, _ = existing
            _legacy_session_store[session_id] = (memory, now)
            return memory

        memory = ConversationMemory(max_turns=5)
        _legacy_session_store[session_id] = (memory, now)
        _evict_lru_if_full()
        return memory


def _save_memory_if_needed(session_id: str, memory: ConversationMemory, channel: str = "telegram", mahasiswa_id: Optional[str] = None) -> None:
    """Save memory to persistent storage if using database sessions."""
    if settings.USE_DATABASE_SESSIONS:
        try:
            _session_store.save_memory(session_id, memory, channel=channel, mahasiswa_id=mahasiswa_id)
        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")


def clear_session(session_id: str) -> bool:
    """Clear conversation memory for a session"""
    if settings.USE_DATABASE_SESSIONS:
        return _session_store.delete_session(session_id)
    
    with _legacy_session_lock:
        if session_id in _legacy_session_store:
            del _legacy_session_store[session_id]
            logger.info(f"Session {session_id} cleared")
            return True
    return False


def get_session_stats() -> Dict[str, Any]:
    """Get statistics about active sessions"""
    if settings.USE_DATABASE_SESSIONS:
        return _session_store.get_session_stats()
    
    with _legacy_session_lock:
        return {
            "active_sessions": len(_legacy_session_store),
            "total_turns": sum(m.turn_count for m, _ in _legacy_session_store.values()),
            "sessions": list(_legacy_session_store.keys()),
        }


def cleanup_sessions() -> int:
    """Manually trigger session cleanup. Returns number of sessions cleaned."""
    if settings.USE_DATABASE_SESSIONS:
        return _session_store.cleanup_idle_sessions()
    
    now = time.time()
    with _legacy_session_lock:
        return _evict_idle_sessions(now)


def chat(query: str, session_id: str, username: str, channel: str = "telegram", mahasiswa_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Main chat function implementing Retrieval-First Architecture.
    """
    if not query or not query.strip():
        return {"answer": "Pertanyaan tidak boleh kosong.", "num_docs": 0, "error": "empty_query"}

    if not session_id:
        return {"answer": "Session ID diperlukan.", "num_docs": 0, "error": "missing_session_id"}

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
            memory = get_or_create_memory(session_id)
            memory.add_user_turn(question)
            
            t_rewrite_start = time.time()
            resolved_query, rewrite_method = reformulate_query(normalized_query, memory)
            t_rewrite_end = time.time()
            logger.info(f"[session={session_id}] [Rewrite] {rewrite_method}: '{normalized_query}' → '{resolved_query}' [⏱️ {t_rewrite_end - t_rewrite_start:.2f}s]")
            
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

        # FAST PATH: Load memory here if not loaded yet
        if memory is None:
            memory = get_or_create_memory(session_id)
            memory.add_user_turn(question)
            
        # 4. LLM Generation
        t_gen_start = time.time()
        result = _rag_chain.invoke_with_history(
            question=question,
            context_documents=retrieval_docs,
            conversation_history=memory.get_history_for_llm(),
        )
        t_gen_end = time.time()
        logger.info(f"[session={session_id}] Generation time [⏱️ {t_gen_end - t_gen_start:.2f}s]")
        
        answer = result["answer"]
        
        # 5. Save state
        if retrieval_docs:
            memory.add_assistant_turn(
                content=answer,
                retrieved_doc_contents=[p["content"] for p in retrieval_docs],
            )
        else:
            memory.add_assistant_turn(content=answer)
            
        _save_memory_if_needed(session_id, memory, channel=channel, mahasiswa_id=mahasiswa_id)
        
        t_total_end = time.time()
        logger.info(f"[session={session_id}] Total process time [⏱️ {t_total_end - t_start:.2f}s]")
        
        # 6. Catat chat log
        try:
            if settings.USE_DATABASE_SESSIONS:
                user_id_log = str(mahasiswa_id) if mahasiswa_id else str(session_id)
                # Gunakan supabase client dari session_store
                _session_store._supabase.table("chat_logs").insert({
                    "user_id": user_id_log,
                    "username": username,
                    "question": question,
                    "answer": answer,
                }).execute()
        except Exception as e:
            logger.error(f"Gagal menyimpan log chat untuk user {user_id_log}: {e}")

        return {
            "answer": answer,
            "num_docs": len(retrieval_docs),
            "rewrite_method": rewrite_method,
            "sources": [
                {
                    "section": p.get("section", ""),
                    "title": p.get("title", ""),
                    "parent_id": p.get("parent_id", ""),
                    "score": p.get("cross_encoder_score", 0.0),
                }
                for p in retrieval_docs[:3]
            ] if retrieval_docs else [],
        }
        
    except Exception as e:
        logger.error(f"[session={session_id}] Error processing query: {e}", exc_info=True)
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
