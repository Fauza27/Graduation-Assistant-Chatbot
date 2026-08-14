"""
Strategy pattern untuk session storage dengan interface abstract.
Eliminasi branching berulang dalam ai_services.py.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import time
from threading import Lock
from loguru import logger

from src.generation.memory import ConversationMemory
from config.settings import get_settings


class SessionStore(ABC):
    """Abstract base class untuk session storage strategies."""
    
    @abstractmethod
    def load_memory(self, session_id: str, mahasiswa_id: Optional[str] = None) -> ConversationMemory:
        """Load conversation memory for a session."""
        pass
    
    @abstractmethod
    def save_memory(self, session_id: str, memory: ConversationMemory, channel: str = "telegram", mahasiswa_id: Optional[str] = None) -> None:
        """Save conversation memory."""
        pass
    
    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        pass
    
    @abstractmethod
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        pass
    
    @abstractmethod
    def cleanup_idle_sessions(self) -> int:
        """Clean up idle sessions."""
        pass


class DatabaseSessionStrategy(SessionStore):
    """Database-backed session storage strategy."""
    
    def __init__(self):
        from src.services.session_store import get_session_store
        self._store = get_session_store()
        logger.info("Using database-backed session storage strategy")
    
    def load_memory(self, session_id: str, mahasiswa_id: Optional[str] = None) -> ConversationMemory:
        return self._store.load_memory(session_id, mahasiswa_id)
    
    def save_memory(self, session_id: str, memory: ConversationMemory, channel: str = "telegram", mahasiswa_id: Optional[str] = None) -> None:
        self._store.save_memory(session_id, memory, channel, mahasiswa_id)
    
    def delete_session(self, session_id: str) -> bool:
        return self._store.delete_session(session_id)
    
    def get_session_stats(self) -> Dict[str, Any]:
        return self._store.get_session_stats()
    
    def cleanup_idle_sessions(self) -> int:
        return self._store.cleanup_idle_sessions()


class LegacyInMemorySessionStrategy(SessionStore):
    """Legacy in-memory session storage strategy."""
    
    def __init__(self):
        self._session_store: dict[str, tuple[ConversationMemory, float]] = {}
        self._session_lock = Lock()
        self._settings = get_settings()
        logger.info("Using legacy in-memory session storage strategy")
    
    def load_memory(self, session_id: str, mahasiswa_id: Optional[str] = None) -> ConversationMemory:
        """Get or create conversation memory for a session."""
        now = time.time()
        with self._session_lock:
            self._evict_idle_sessions(now)

            existing = self._session_store.get(session_id)
            if existing is not None:
                memory, _ = existing
                self._session_store[session_id] = (memory, now)
                return memory

            memory = ConversationMemory(max_turns=5)
            self._session_store[session_id] = (memory, now)
            self._evict_lru_if_full()
            return memory
    
    def save_memory(self, session_id: str, memory: ConversationMemory, channel: str = "telegram", mahasiswa_id: Optional[str] = None) -> None:
        """Save memory to in-memory store (updates timestamp)."""
        now = time.time()
        with self._session_lock:
            self._session_store[session_id] = (memory, now)
    
    def delete_session(self, session_id: str) -> bool:
        """Clear conversation memory for a session."""
        with self._session_lock:
            if session_id in self._session_store:
                del self._session_store[session_id]
                logger.info(f"Session {session_id} cleared")
                return True
        return False
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about active sessions."""
        with self._session_lock:
            return {
                "active_sessions": len(self._session_store),
                "total_turns": sum(m.turn_count for m, _ in self._session_store.values()),
                "sessions": list(self._session_store.keys()),
                "storage_type": "legacy_in_memory"
            }
    
    def cleanup_idle_sessions(self) -> int:
        """Manually trigger session cleanup."""
        now = time.time()
        with self._session_lock:
            return self._evict_idle_sessions(now)
    
    def _evict_idle_sessions(self, now: float) -> int:
        """Hapus session yang idle melebihi SESSION_CLEANUP_INTERVAL detik."""
        ttl = self._settings.SESSION_CLEANUP_INTERVAL
        expired = [sid for sid, (_, last_ts) in self._session_store.items() if now - last_ts > ttl]
        for sid in expired:
            self._session_store.pop(sid, None)
        if expired:
            logger.info(f"Evicted {len(expired)} idle session(s)")
        return len(expired)
    
    def _evict_lru_if_full(self) -> None:
        """Jika store sudah penuh, hapus session paling lama tidak diakses."""
        cap = self._settings.MAX_ACTIVE_SESSIONS
        if len(self._session_store) <= cap:
            return
        # Sort by last_access_ts ascending; buang sampai cap.
        overflow = len(self._session_store) - cap
        sorted_items = sorted(self._session_store.items(), key=lambda kv: kv[1][1])
        for sid, _ in sorted_items[:overflow]:
            self._session_store.pop(sid, None)
        logger.info(f"Evicted {overflow} LRU session(s) due to MAX_ACTIVE_SESSIONS cap")


def create_session_store() -> SessionStore:
    """
    Factory function untuk membuat session store strategy.
    Dipanggil sekali saat startup, tidak ada branching berulang.
    """
    settings = get_settings()
    
    if settings.USE_DATABASE_SESSIONS:
        try:
            return DatabaseSessionStrategy()
        except Exception as e:
            logger.error(f"Failed to initialize database session store: {e}")
            logger.warning("Falling back to in-memory session storage")
            # Fall back to in-memory strategy
    
    return LegacyInMemorySessionStrategy()