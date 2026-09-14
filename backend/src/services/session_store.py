from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional

from loguru import logger
from supabase import Client, create_client

from config.settings import get_settings
from src.services.session_strategy import SessionAccessError, verify_session_owner
from src.generation.memory import (
    ConversationMemory,
    create_conversation_memory,
    get_memory_config,
)


settings = get_settings()

DEFAULT_CACHE_SIZE = 50


@dataclass
class CachedSession:
    """Session yang disimpan sementara di memory."""
    memory: ConversationMemory
    owner_id: Optional[str]


@dataclass(frozen=True)
class _OwnerLookup:
    """Hasil lookup kepemilikan session dari cache/database."""
    found: bool
    owner_id: Optional[str]


class SessionCache:
    """Thread-safe LRU cache untuk conversation sessions."""

    def __init__(self, capacity: int):
        self._capacity = max(1, capacity)
        self._items: OrderedDict[str, CachedSession] = OrderedDict()
        self._lock = Lock()

    def get(
        self,
        session_id: str,
        owner_id: Optional[str] = None,
    ) -> Optional[ConversationMemory]:
        with self._lock:
            session = self._items.get(session_id)

            if session is None:
                return None

            verify_session_owner(session.owner_id, owner_id)

            # Mark as recently used.
            self._items.move_to_end(session_id)

            return session.memory

    def peek_owner(self, session_id: str) -> Optional[str]:
        """
        Ambil owner_id dari cache tanpa verifikasi dan tanpa mengubah LRU order.

        Digunakan oleh _get_existing_owner sebagai fast-path sebelum
        melakukan query database.
        """
        with self._lock:
            session = self._items.get(session_id)
            if session is None:
                return None
            return session.owner_id

    def peek_entry(self, session_id: str) -> Optional[CachedSession]:
        """
        Ambil CachedSession dari cache tanpa verifikasi dan tanpa mengubah LRU order.

        Memungkinkan caller membedakan antara cache-miss vs session ada tanpa owner.
        """
        with self._lock:
            return self._items.get(session_id)

    def put(
        self,
        session_id: str,
        memory: ConversationMemory,
        owner_id: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._items[session_id] = CachedSession(
                memory=memory,
                owner_id=owner_id,
            )

            self._items.move_to_end(session_id)

            while len(self._items) > self._capacity:
                evicted_id, _ = self._items.popitem(last=False)
                logger.debug(
                    f"Evicted LRU session {evicted_id} from cache"
                )

    def remove(self, session_id: str) -> None:
        with self._lock:
            self._items.pop(session_id, None)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "cache_size": len(self._items),
                "cache_capacity": self._capacity,
                "cached_sessions": list(self._items.keys()),
            }

    def remove_idle(
        self,
        idle_session_ids: list[str],
    ) -> None:
        with self._lock:
            for session_id in idle_session_ids:
                self._items.pop(session_id, None)

class DatabaseSessionStore:
    """
    Mengelola conversation session yang disimpan di Supabase
    dengan LRU cache untuk akses cepat.
    """

    def __init__(self, cache_size: int = DEFAULT_CACHE_SIZE):
        self._supabase = self._create_supabase_client()
        self._cache = SessionCache(cache_size)

        self._test_connection()

    def load_memory(
        self,
        session_id: str,
        mahasiswa_id: Optional[str] = None,
    ) -> ConversationMemory:
        """Ambil memory session dari cache atau database."""

        memory = self._load_from_cache(session_id, mahasiswa_id)

        if memory is not None:
            logger.debug(f"Session {session_id} loaded from cache")
            return memory

        memory, owner_id = self._load_from_database(
            session_id=session_id,
            mahasiswa_id=mahasiswa_id,
        )

        self._cache.put(
            session_id=session_id,
            memory=memory,
            owner_id=owner_id,
        )

        self._update_last_access(session_id)

        return memory

    def save_memory(
        self,
        session_id: str,
        memory: ConversationMemory,
        channel: str = "telegram",
        mahasiswa_id: Optional[str] = None,
    ) -> None:
        """Simpan memory ke database dan update cache."""

        owner_lookup = self._get_existing_owner(session_id)
        existing_owner = owner_lookup.owner_id if owner_lookup.found else None
        verify_session_owner(
            session_owner_id=existing_owner,
            requested_owner_id=mahasiswa_id,
        )

        # Pertahankan owner_id asli agar tidak bisa dibajak.
        effective_owner = existing_owner or mahasiswa_id

        payload = self._build_session_payload(
            session_id=session_id,
            memory=memory,
            channel=channel,
            mahasiswa_id=effective_owner,
        )

        try:
            (
                self._supabase
                .table("conversation_sessions")
                .upsert(payload)
                .execute()
            )

            self._cache.put(
                session_id=session_id,
                memory=memory,
                owner_id=effective_owner,
            )

            logger.debug(
                f"Session {session_id} saved "
                f"with {memory.turn_count} turn(s)"
            )

        except SessionAccessError:
            raise

        except Exception as exc:
            logger.error(
                f"Failed to save session {session_id}: {exc}"
            )
            raise

    def delete_session(
        self,
        session_id: str,
        mahasiswa_id: Optional[str] = None,
    ) -> bool:
        """
        Hapus session hanya jika session dimiliki oleh user terkait.

        Melempar SessionAccessError jika mahasiswa_id tidak cocok
        dengan owner session — konsisten dengan InMemorySessionStrategy.
        Mengembalikan False jika session memang tidak ditemukan.
        """

        # Verifikasi ownership sebelum delete untuk mendeteksi
        # percobaan IDOR sebagai security event (bukan silent fail).
        owner_lookup = self._get_existing_owner(session_id)

        if not owner_lookup.found:
            # Session tidak ditemukan di cache maupun DB.
            return False

        verify_session_owner(
            session_owner_id=owner_lookup.owner_id,
            requested_owner_id=mahasiswa_id,
        )

        try:
            result = (
                self._supabase
                .table("conversation_sessions")
                .delete()
                .eq("session_id", session_id)
                .execute()
            )

            self._cache.remove(session_id)

            deleted = bool(result.data)

            if deleted:
                logger.info(f"Session {session_id} deleted")

            return deleted

        except SessionAccessError:
            raise

        except Exception as exc:
            logger.error(
                f"Failed to delete session {session_id}: {exc}"
            )
            return False

    def cleanup_idle_sessions(
        self,
        ttl_seconds: Optional[int] = None,
    ) -> int:
        """Hapus session yang sudah idle terlalu lama."""
        ttl_seconds = (
            ttl_seconds
            if ttl_seconds is not None
            else settings.SESSION_CLEANUP_INTERVAL
        )

        try:
            result = (
                self._supabase
                .rpc(
                    "cleanup_idle_sessions",
                    {"p_ttl_seconds": ttl_seconds},
                )
                .execute()
            )
            cleaned_count = result.data or 0
            if cleaned_count:
                logger.info("Cleaned up {} idle session(s)", cleaned_count)
            return cleaned_count
        except Exception as exc:
            logger.error("Failed to cleanup idle sessions: {}", exc)
            return 0

    def get_session_stats(self) -> Dict[str, Any]:
        """Ambil statistik session dari database dan cache."""

        try:
            result = (
                self._supabase
                .rpc("get_session_statistics")
                .execute()
            )

            database_stats = (
                result.data[0]
                if result.data
                else {}
            )

            return {
                "storage_type": "database",
                **database_stats,
                **self._cache.stats(),
            }

        except Exception as exc:
            logger.error(
                f"Failed to get session stats: {exc}"
            )
            return {"error": str(exc)}

    def log_chat_interaction(
        self,
        user_id: str,
        username: str,
        question: str,
        answer: str,
    ) -> None:
        """Simpan log chat tanpa mengganggu alur utama."""

        try:
            (
                self._supabase
                .table("chat_logs")
                .insert({
                    "user_id": user_id,
                    "username": username,
                    "question": question,
                    "answer": answer,
                })
                .execute()
            )

        except Exception as exc:
            logger.error(
                f"Gagal menyimpan log chat "
                f"untuk user {user_id}: {exc}"
            )

    def list_sessions_for_user(
        self,
        mahasiswa_id: str,
    ) -> list[dict[str, Any]]:
        """
        List all sessions for a specific user through proper interface.
        
        Returns list of session summaries with session_id, title, and last_access.
        """
        try:
            result = (
                self._supabase
                .table("conversation_sessions")
                .select("session_id, last_access, turns")
                .eq("mahasiswa_id", mahasiswa_id)
                .order("last_access", desc=True)
                .execute()
            )

            sessions = []
            for row in result.data or []:
                turns = ConversationMemory.serialized_turns(row.get("turns"))
                title = "Sesi Tanpa Judul"
                
                # Extract title from first user message
                for turn in turns:
                    if turn.get("role") == "user":
                        content = turn.get("content", "")
                        title = content[:40] + ("..." if len(content) > 40 else "")
                        break

                sessions.append({
                    "session_id": row.get("session_id"),
                    "title": title,
                    "last_access": row.get("last_access"),
                })

            return sessions

        except Exception as exc:
            logger.error(
                f"Failed to list sessions for user {mahasiswa_id}: {exc}"
            )
            return []

    def get_session_details_for_user(
        self,
        session_id: str,
        mahasiswa_id: str,
    ) -> dict[str, Any] | None:
        """
        Get detailed session data for a specific user through proper interface.
        
        Returns session details or None if not found/forbidden.
        """
        try:
            result = (
                self._supabase
                .table("conversation_sessions")
                .select("turns")
                .eq("session_id", session_id)
                .eq("mahasiswa_id", mahasiswa_id)
                .execute()
            )

            if not result.data:
                return None

            turns = ConversationMemory.serialized_turns(
                result.data[0].get("turns")
            )
            messages = []
            
            for turn in turns:
                role = turn.get("role")
                if role == "assistant":
                    role = "bot"

                messages.append({
                    "role": role,
                    "text": turn.get("content"),
                    "sources": turn.get("sources", turn.get("retrieved_doc_contents", [])),
                })

            return {"messages": messages}

        except Exception as exc:
            logger.error(
                f"Failed to get session details {session_id} for user {mahasiswa_id}: {exc}"
            )
            return None

    @staticmethod
    def _create_supabase_client() -> Client:
        return create_client(
            settings.supabase_url,
            settings.supabase_service_key,
        )

    def _test_connection(self) -> None:
        try:
            (
                self._supabase
                .table("conversation_sessions")
                .select("session_id")
                .limit(1)
                .execute()
            )

            logger.info(
                "Database session store initialized successfully"
            )

        except Exception as exc:
            logger.error(
                f"Failed to connect to session database: {exc}"
            )
            raise RuntimeError(
                f"Session database connection failed: {exc}"
            ) from exc

    def _get_existing_owner(
        self,
        session_id: str,
    ) -> _OwnerLookup:
        """
        Baca status keberadaan dan owner_id sesi dari cache (fast-path)
        atau database (slow-path).

        Mengembalikan _OwnerLookup(found=False, owner_id=None) jika sesi
        belum pernah ada, sehingga caller bisa membedakan antara
        "sesi belum ada" dan "sesi ada tanpa owner (Telegram)".
        """
        # Fast-path: cek cache memory tanpa network trip.
        cached_entry = self._cache.peek_entry(session_id)
        if cached_entry is not None:
            return _OwnerLookup(found=True, owner_id=cached_entry.owner_id)

        # Slow-path: query database.
        try:
            result = (
                self._supabase
                .table("conversation_sessions")
                .select("mahasiswa_id")
                .eq("session_id", session_id)
                .single()
                .execute()
            )

        except Exception as exc:
            exc_str = str(exc)

            # PGRST116 = "The result contains 0 rows" dari PostgREST —
            # session memang belum ada, bukan error koneksi.
            if "PGRST116" in exc_str or "contains 0 rows" in exc_str:
                return _OwnerLookup(found=False, owner_id=None)

            logger.error(
                f"Failed to read owner for session {session_id}: {exc}"
            )
            raise

        if not result.data:
            return _OwnerLookup(found=False, owner_id=None)

        return _OwnerLookup(found=True, owner_id=result.data.get("mahasiswa_id"))

    def _load_from_database(
        self,
        session_id: str,
        mahasiswa_id: Optional[str],
    ) -> tuple[ConversationMemory, Optional[str]]:
        """
        Load session dari database.

        Membedakan dua kondisi:
        - Session tidak ditemukan (PostgREST PGRST116): kembalikan memory baru.
        - Error lain (koneksi, timeout, dsb): re-raise exception asli agar
          classify_exception mengenali error Supabase dengan presisi.
        """
        try:
            result = (
                self._supabase
                .table("conversation_sessions")
                .select("turns, mahasiswa_id")
                .eq("session_id", session_id)
                .single()
                .execute()
            )

        except Exception as exc:
            exc_str = str(exc)

            # PGRST116 = "The result contains 0 rows" dari PostgREST —
            # ini bukan error, hanya sesi baru.
            if "PGRST116" in exc_str or "contains 0 rows" in exc_str:
                logger.debug(
                    f"Session {session_id} not found in database, "
                    "creating new memory"
                )
                return (
                    create_conversation_memory(),
                    mahasiswa_id,
                )

            logger.error(
                f"Database error while loading session {session_id}: {exc}"
            )
            raise

        data = result.data

        if not data:
            return (
                create_conversation_memory(),
                mahasiswa_id,
            )

        owner_id = data.get("mahasiswa_id")

        verify_session_owner(
            session_owner_id=owner_id,
            requested_owner_id=mahasiswa_id,
        )

        turns = data.get("turns")

        if not turns:
            return (
                create_conversation_memory(),
                owner_id,
            )

        memory = ConversationMemory.from_dict(
            turns,
            **get_memory_config(),
        )

        return memory, owner_id

    def _load_from_cache(
        self,
        session_id: str,
        mahasiswa_id: Optional[str],
    ) -> Optional[ConversationMemory]:
        return self._cache.get(
            session_id=session_id,
            owner_id=mahasiswa_id,
        )

    @staticmethod
    def _build_session_payload(
        session_id: str,
        memory: ConversationMemory,
        channel: str,
        mahasiswa_id: Optional[str],
    ) -> Dict[str, Any]:

        payload = {
            "session_id": session_id,
            "turns": memory.to_dict(),
            "channel": channel,
            "last_access": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        if mahasiswa_id:
            payload["mahasiswa_id"] = mahasiswa_id

        return payload

    def _update_last_access(self, session_id: str) -> None:
        """Update timestamp tanpa menggagalkan operasi utama."""

        try:
            (
                self._supabase
                .table("conversation_sessions")
                .update({
                    "last_access": datetime.now(
                        timezone.utc
                    ).isoformat()
                })
                .eq("session_id", session_id)
                .execute()
            )

        except Exception as exc:
            logger.debug(
                f"Failed to update last_access "
                f"for {session_id}: {exc}"
            )


def get_session_store() -> DatabaseSessionStore:
    """
    Kembalikan instance DatabaseSessionStore.

    Digunakan oleh session_strategy.create_session_store()
    dan endpoint yang memerlukan akses langsung ke database.
    """
    return DatabaseSessionStore()
