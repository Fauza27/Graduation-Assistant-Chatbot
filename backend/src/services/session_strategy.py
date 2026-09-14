"""
Session storage strategies.

Strategy Pattern untuk memisahkan cara penyimpanan session
dari business logic aplikasi.

Strategies:
- DatabaseSessionStrategy: menggunakan DatabaseSessionStore.
- InMemorySessionStrategy: menyimpan session di memory proses.

Factory:
- create_session_store(): memilih strategy berdasarkan konfigurasi.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from dataclasses import dataclass
from threading import Lock
from time import time
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from config.settings import get_settings
from src.generation.memory import ConversationMemory, create_conversation_memory
from src.monitoring.errors import SessionAccessError

if TYPE_CHECKING:
    from src.services.session_store import DatabaseSessionStore


@dataclass
class SessionEntry:
    """
    Data session yang disimpan oleh in-memory strategy.

    Menyatukan seluruh metadata session dalam satu object
    agar tidak perlu menggunakan beberapa dictionary paralel.
    """

    memory: ConversationMemory
    last_access: float
    owner_id: Optional[str] = None


class SessionStore(ABC):
    """
    Contract untuk seluruh implementasi session storage.
    """

    @abstractmethod
    def load_memory(
        self,
        session_id: str,
        mahasiswa_id: Optional[str] = None,
    ) -> ConversationMemory:
        """Load memory untuk sebuah session."""
        ...

    @abstractmethod
    def save_memory(
        self,
        session_id: str,
        memory: ConversationMemory,
        channel: str = "telegram",
        mahasiswa_id: Optional[str] = None,
    ) -> None:
        """Simpan memory untuk sebuah session."""
        ...

    @abstractmethod
    def delete_session(
        self,
        session_id: str,
        mahasiswa_id: Optional[str] = None,
    ) -> bool:
        """Hapus sebuah session."""
        ...

    @abstractmethod
    def get_session_stats(self) -> dict[str, Any]:
        """Ambil statistik session."""
        ...

    @abstractmethod
    def cleanup_cache(self) -> int:
        """Bersihkan state session yang hanya tersimpan di memory proses."""
        ...

    def cleanup_idle_sessions(self) -> int:
        """Alias kompatibilitas; cleanup tidak boleh menghapus session database."""
        return self.cleanup_cache()

    def log_chat_interaction(
        self,
        user_id: str,
        username: str,
        question: str,
        answer: str,
    ) -> None:
        """
        Optional operation.

        Default no-op agar strategy yang tidak memiliki
        backing database tidak wajib melakukan logging.
        """
        return None

    @abstractmethod
    def list_sessions_for_user(
        self,
        mahasiswa_id: str,
    ) -> list[dict[str, Any]]:
        """List all sessions for a specific user."""
        ...

    @abstractmethod
    def get_session_details_for_user(
        self,
        session_id: str,
        mahasiswa_id: str,
    ) -> dict[str, Any] | None:
        """Get detailed session data for a specific user."""
        ...


def verify_session_owner(
    session_owner_id: Optional[str],
    requested_owner_id: Optional[str],
) -> None:
    """
    Pastikan user hanya dapat mengakses session miliknya (IDOR protection).

    Aturan:
    - Jika sesi belum memiliki owner (session_owner_id is None), request diizinkan
      (baik sesi Telegram murni maupun klaim kepemilikan oleh user website terautentikasi).
    - Jika sesi memiliki owner (session_owner_id is not None), request hanya diizinkan
      jika requested_owner_id sama persis dengan session_owner_id.
    - Request tanpa identitas (requested_owner_id is None) dilarang mengakses sesi berpemilik.
    """
    if session_owner_id is None:
        return

    if session_owner_id == requested_owner_id:
        return

    raise SessionAccessError(
        session_owner_id=session_owner_id,
        requested_owner_id=requested_owner_id,
    )


class DatabaseSessionStrategy(SessionStore):
    """
    Strategy untuk session yang disimpan menggunakan database.

    DatabaseSessionStore menangani detail database dan cache,
    sedangkan class ini hanya berfungsi sebagai adapter ke
    SessionStore interface.
    """

    def __init__(self, store: "DatabaseSessionStore") -> None:
        self._store = store
        logger.info("Using database-backed session storage strategy")

    def load_memory(
        self,
        session_id: str,
        mahasiswa_id: Optional[str] = None,
    ) -> ConversationMemory:
        return self._store.load_memory(
            session_id,
            mahasiswa_id,
        )

    def save_memory(
        self,
        session_id: str,
        memory: ConversationMemory,
        channel: str = "telegram",
        mahasiswa_id: Optional[str] = None,
    ) -> None:
        self._store.save_memory(
            session_id,
            memory,
            channel,
            mahasiswa_id,
        )

    def delete_session(
        self,
        session_id: str,
        mahasiswa_id: Optional[str] = None,
    ) -> bool:
        return self._store.delete_session(
            session_id,
            mahasiswa_id,
        )

    def get_session_stats(self) -> dict[str, Any]:
        return self._store.get_session_stats()

    def cleanup_cache(self) -> int:
        return self._store.cleanup_cache()

    def log_chat_interaction(
        self,
        user_id: str,
        username: str,
        question: str,
        answer: str,
    ) -> None:
        self._store.log_chat_interaction(
            user_id,
            username,
            question,
            answer,
        )

    def list_sessions_for_user(
        self,
        mahasiswa_id: str,
    ) -> list[dict[str, Any]]:
        return self._store.list_sessions_for_user(mahasiswa_id)

    def get_session_details_for_user(
        self,
        session_id: str,
        mahasiswa_id: str,
    ) -> dict[str, Any] | None:
        return self._store.get_session_details_for_user(session_id, mahasiswa_id)


class InMemorySessionStrategy(SessionStore):
    """
    Strategy untuk session yang disimpan di memory proses.

    Cocok untuk:
    - development
    - testing
    - fallback yang memang diizinkan oleh konfigurasi

    Session akan dihapus berdasarkan:
    - TTL / idle timeout
    - MAX_ACTIVE_SESSIONS
    """

    def __init__(
        self,
        max_sessions: int,
        ttl_seconds: int,
    ):
        self._sessions: dict[str, SessionEntry] = {}
        self._max_sessions = max(1, max_sessions)
        self._ttl_seconds = max(1, ttl_seconds)
        self._lock = Lock()

        logger.info(
            "Using in-memory session storage strategy"
        )

    def load_memory(
        self,
        session_id: str,
        mahasiswa_id: Optional[str] = None,
    ) -> ConversationMemory:
        """
        Ambil memory session.

        Jika session belum ada, buat memory baru.
        """
        now = time()

        with self._lock:
            self._remove_idle_sessions(now)

            entry = self._sessions.get(session_id)

            if entry is not None:
                verify_session_owner(
                    session_owner_id=entry.owner_id,
                    requested_owner_id=mahasiswa_id,
                )

                entry.last_access = now

                if entry.owner_id is None:
                    entry.owner_id = mahasiswa_id

                return entry.memory

            memory = create_conversation_memory()

            self._sessions[session_id] = SessionEntry(
                memory=memory,
                last_access=now,
                owner_id=mahasiswa_id,
            )

            self._evict_lru_if_needed()

            return memory

    def save_memory(
        self,
        session_id: str,
        memory: ConversationMemory,
        channel: str = "telegram",
        mahasiswa_id: Optional[str] = None,
    ) -> None:
        """
        Simpan/update memory session.

        Ownership tetap diperiksa jika session sudah ada.
        """
        now = time()

        with self._lock:
            entry = self._sessions.get(session_id)

            if entry is not None:
                verify_session_owner(
                    session_owner_id=entry.owner_id,
                    requested_owner_id=mahasiswa_id,
                )

                owner_id = entry.owner_id or mahasiswa_id
            else:
                owner_id = mahasiswa_id

            self._sessions[session_id] = SessionEntry(
                memory=memory,
                last_access=now,
                owner_id=owner_id,
            )

            self._evict_lru_if_needed()

    def delete_session(
        self,
        session_id: str,
        mahasiswa_id: Optional[str] = None,
    ) -> bool:
        """
        Hapus session jika session ditemukan dan user berhak
        menghapusnya.
        """
        with self._lock:
            entry = self._sessions.get(session_id)

            if entry is None:
                return False

            verify_session_owner(
                session_owner_id=entry.owner_id,
                requested_owner_id=mahasiswa_id,
            )

            del self._sessions[session_id]

            logger.info(
                "Session {} deleted",
                session_id,
            )

            return True

    def get_session_stats(self) -> dict[str, Any]:
        """Ambil statistik session aktif."""
        with self._lock:
            return {
                "active_sessions": len(self._sessions),
                "total_turns": sum(
                    entry.memory.turn_count
                    for entry in self._sessions.values()
                ),
                "sessions": list(self._sessions.keys()),
                "storage_type": "in_memory",
            }

    def cleanup_cache(self) -> int:
        """Hapus entry cache in-memory yang sudah idle melebihi TTL."""
        with self._lock:
            return self._remove_idle_sessions(time())

    def _remove_idle_sessions(self, now: float) -> int:
        """Hapus semua session yang melebihi TTL."""
        expired_ids = [
            session_id
            for session_id, entry in self._sessions.items()
            if now - entry.last_access > self._ttl_seconds
        ]

        for session_id in expired_ids:
            del self._sessions[session_id]

        if expired_ids:
            logger.info(
                "Evicted {} idle session(s)",
                len(expired_ids),
            )

        return len(expired_ids)

    def _evict_lru_if_needed(self) -> None:
        """
        Hapus session paling lama digunakan jika kapasitas penuh.

        Sorting hanya dilakukan ketika jumlah session melewati
        batas maksimum, bukan pada setiap operasi read.
        """
        overflow = len(self._sessions) - self._max_sessions

        if overflow <= 0:
            return

        oldest_sessions = sorted(
            self._sessions.items(),
            key=lambda item: item[1].last_access,
        )[:overflow]

        for session_id, _ in oldest_sessions:
            del self._sessions[session_id]

        logger.info(
            "Evicted {} LRU session(s) due to "
            "MAX_ACTIVE_SESSIONS cap",
            overflow,
        )

    def list_sessions_for_user(
        self,
        mahasiswa_id: str,
    ) -> list[dict[str, Any]]:
        """List all sessions for a specific user (in-memory implementation)."""
        with self._lock:
            sessions = []
            
            for session_id, entry in self._sessions.items():
                if entry.owner_id != mahasiswa_id:
                    continue
                
                # Extract title from first user message
                title = "Sesi Tanpa Judul"
                for turn in entry.memory.turns:
                    if turn.role == "user":
                        content = turn.content
                        title = content[:40] + ("..." if len(content) > 40 else "")
                        break
                
                sessions.append({
                    "session_id": session_id,
                    "title": title,
                    "last_access": datetime.fromtimestamp(entry.last_access, tz=timezone.utc).isoformat(),
                })
            
            # Sort by last access (most recent first)
            sessions.sort(key=lambda s: s["last_access"], reverse=True)
            return sessions

    def get_session_details_for_user(
        self,
        session_id: str,
        mahasiswa_id: str,
    ) -> dict[str, Any] | None:
        """Get detailed session data for a specific user (in-memory implementation)."""
        with self._lock:
            entry = self._sessions.get(session_id)
            
            if entry is None or entry.owner_id != mahasiswa_id:
                return None
            
            messages = []
            for turn in entry.memory.turns:
                role = turn.role
                if role == "assistant":
                    role = "bot"

                messages.append({
                    "role": role,
                    "text": turn.content,
                    "sources": turn.sources,
                })

            return {"messages": messages}


def create_session_store() -> SessionStore:
    settings = get_settings()

    if not settings.USE_DATABASE_SESSIONS:
        return InMemorySessionStrategy(
            max_sessions=settings.MAX_ACTIVE_SESSIONS,
            ttl_seconds=settings.SESSION_CLEANUP_INTERVAL,
        )

    try:
        from src.services.session_store import get_session_store

        return DatabaseSessionStrategy(get_session_store())

    except Exception as exc:
        logger.critical(
            "CRITICAL: Failed to initialize database session store! "
            "Halting startup (fail-fast) to prevent session fragmentation in multi-worker environment: {}",
            exc,
        )

        raise RuntimeError(
            "Database session store initialization failed"
        ) from exc
