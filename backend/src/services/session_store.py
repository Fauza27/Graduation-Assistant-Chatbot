"""
Database-backed session storage for conversation memory.
Replaces in-memory session store with persistent Supabase storage.
"""

import time
from typing import Dict, Any, Optional
from threading import Lock
from functools import lru_cache
from loguru import logger
from supabase import create_client, Client
from datetime import datetime, timezone
from fastapi import HTTPException

from src.generation.memory import ConversationMemory
from config.settings import get_settings

settings = get_settings()


class DatabaseSessionStore:
    """
    Database-backed session storage with in-memory LRU cache for performance.
    
    Features:
    - Persistent storage in Supabase
    - Hot LRU cache for active sessions
    - Automatic TTL cleanup
    - Thread-safe operations
    """
    
    def __init__(self, cache_size: int = 50):
        self._supabase = self._get_supabase_client()
        self._cache: Dict[str, ConversationMemory] = {}
        self._cache_access: Dict[str, float] = {}
        self._cache_size = cache_size
        self._cache_lock = Lock()
        
        # Test database connection
        self._test_connection()
    
    @lru_cache(maxsize=1)
    def _get_supabase_client(self) -> Client:
        """Get cached Supabase client."""
        return create_client(settings.supabase_url, settings.supabase_service_key)
    
    def _test_connection(self) -> None:
        """Test database connection and table existence."""
        try:
            result = self._supabase.table("conversation_sessions").select("session_id").limit(1).execute()
            logger.info("Database session store initialized successfully")
        except Exception as e:
            logger.error(f"Failed to connect to session database: {e}")
            raise RuntimeError(f"Session database connection failed: {e}")
    
    def load_memory(self, session_id: str, mahasiswa_id: Optional[str] = None) -> ConversationMemory:
        """
        Load conversation memory for a session and verify ownership.
        
        Args:
            session_id: Unique session identifier
            mahasiswa_id: The ID of the currently logged in user requesting the session
            
        Returns:
            ConversationMemory instance (new if session doesn't exist)
            
        Raises:
            RuntimeError: If session belongs to a different user (IDOR prevention)
        """
        now = time.time()
        
        # Check hot cache first
        with self._cache_lock:
            if session_id in self._cache:
                self._cache_access[session_id] = now
                logger.debug(f"Session {session_id} loaded from cache")
                return self._cache[session_id]
        
        # Load from database
        try:
            result = self._supabase.table("conversation_sessions")\
                .select("turns, mahasiswa_id")\
                .eq("session_id", session_id)\
                .single()\
                .execute()
            
            if result.data:
                # IDOR Protection
                owner_id = result.data.get("mahasiswa_id")
                if mahasiswa_id and owner_id and owner_id != mahasiswa_id:
                    logger.warning(f"IDOR attempt: User {mahasiswa_id} tried to access session {session_id} belonging to {owner_id}")
                    raise HTTPException(status_code=403, detail="Akses ditolak: Anda tidak memiliki akses ke sesi ini.")
                    
                if result.data.get("turns"):
                    turns_data = result.data["turns"]
                    memory = ConversationMemory.from_dict(turns_data, max_turns=5)
                    logger.debug(f"Session {session_id} loaded from database with {len(turns_data)} turns")
                else:
                    memory = ConversationMemory(max_turns=5)
                    logger.debug(f"New session {session_id} created")
            else:
                memory = ConversationMemory(max_turns=5)
                logger.debug(f"New session {session_id} created")
                
        except HTTPException:
            raise  # Let FastAPI handle 403 Forbidden natively
        except Exception as e:
            # If session doesn't exist or any other db error, create new memory
            # (Note: single() raises an error if 0 rows returned)
            if "JSON object requested, multiple (or no) rows returned" in str(e):
                logger.debug(f"New session {session_id} created (row not found)")
            else:
                logger.warning(f"Failed to load session {session_id} from database: {e}")
            memory = ConversationMemory(max_turns=5)
        
        # Add to cache
        with self._cache_lock:
            self._add_to_cache(session_id, memory, now)
        
        # Update last_access in database (fire and forget)
        self._update_last_access(session_id)
        
        return memory
    
    def save_memory(self, session_id: str, memory: ConversationMemory, channel: str = "telegram", mahasiswa_id: Optional[str] = None) -> None:
        """
        Save conversation memory to database.
        
        Args:
            session_id: Unique session identifier
            memory: ConversationMemory to save
            channel: origin of chat
            mahasiswa_id: user id if logged in via website
        """
        try:
            turns_data = memory.to_dict()
            
            payload = {
                "session_id": session_id,
                "turns": turns_data,
                "channel": channel,
                "last_access": datetime.now(timezone.utc).isoformat()
            }
            if mahasiswa_id:
                payload["mahasiswa_id"] = mahasiswa_id

            # Upsert to database
            self._supabase.table("conversation_sessions").upsert(payload).execute()
            
            # Update cache
            with self._cache_lock:
                self._cache[session_id] = memory
                self._cache_access[session_id] = time.time()
            
            logger.debug(f"Session {session_id} saved with {len(turns_data)} turns")
            
        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")
            raise RuntimeError(f"Session save failed: {e}")
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session from database and cache.
        
        Args:
            session_id: Session to delete
            
        Returns:
            True if session was deleted, False if not found
        """
        try:
            # Delete from database
            result = self._supabase.table("conversation_sessions")\
                .delete()\
                .eq("session_id", session_id)\
                .execute()
            
            # Remove from cache
            with self._cache_lock:
                self._cache.pop(session_id, None)
                self._cache_access.pop(session_id, None)
            
            deleted = len(result.data) > 0 if result.data else False
            if deleted:
                logger.info(f"Session {session_id} deleted")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def cleanup_idle_sessions(self, ttl_seconds: Optional[int] = None) -> int:
        """
        Clean up idle sessions from database.
        
        Args:
            ttl_seconds: TTL in seconds (uses settings.SESSION_CLEANUP_INTERVAL if None)
            
        Returns:
            Number of sessions cleaned up
        """
        if ttl_seconds is None:
            ttl_seconds = settings.SESSION_CLEANUP_INTERVAL
        
        try:
            # Call database function for cleanup
            result = self._supabase.rpc("cleanup_idle_sessions", {
                "p_ttl_seconds": ttl_seconds
            }).execute()
            
            cleaned_count = result.data if result.data is not None else 0
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} idle session(s)")
                
                # Also cleanup cache for consistency
                with self._cache_lock:
                    now = time.time()
                    expired_cache_keys = [
                        sid for sid, last_access in self._cache_access.items()
                        if now - last_access > ttl_seconds
                    ]
                    for sid in expired_cache_keys:
                        self._cache.pop(sid, None)
                        self._cache_access.pop(sid, None)
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup idle sessions: {e}")
            return 0
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get session statistics from database.
        
        Returns:
            Dictionary with session statistics
        """
        try:
            # Get database statistics
            result = self._supabase.rpc("get_session_statistics").execute()
            db_stats = result.data[0] if result.data else {}
            
            # Add cache statistics
            with self._cache_lock:
                cache_stats = {
                    "cache_size": len(self._cache),
                    "cache_capacity": self._cache_size,
                    "cached_sessions": list(self._cache.keys())
                }
            
            return {
                **db_stats,
                **cache_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {"error": str(e)}
    
    def _add_to_cache(self, session_id: str, memory: ConversationMemory, access_time: float) -> None:
        """Add session to cache with LRU eviction."""
        self._cache[session_id] = memory
        self._cache_access[session_id] = access_time
        
        # LRU eviction if cache is full
        if len(self._cache) > self._cache_size:
            # Find least recently used session
            lru_session = min(self._cache_access.items(), key=lambda x: x[1])[0]
            self._cache.pop(lru_session, None)
            self._cache_access.pop(lru_session, None)
            logger.debug(f"Evicted LRU session {lru_session} from cache")
    
    def _update_last_access(self, session_id: str) -> None:
        """Update last_access timestamp in database (async, fire and forget)."""
        try:
            self._supabase.table("conversation_sessions")\
                .update({"last_access": datetime.now(timezone.utc).isoformat()})\
                .eq("session_id", session_id)\
                .execute()
        except Exception as e:
            # Don't fail the main operation if this fails
            logger.debug(f"Failed to update last_access for {session_id}: {e}")


# Global instance (singleton pattern)
_database_session_store: Optional[DatabaseSessionStore] = None
_store_lock = Lock()


def get_session_store() -> DatabaseSessionStore:
    """Get global database session store instance (singleton)."""
    global _database_session_store
    
    if _database_session_store is None:
        with _store_lock:
            if _database_session_store is None:
                _database_session_store = DatabaseSessionStore(
                    cache_size=settings.MAX_ACTIVE_SESSIONS // 10  # 10% of max as cache
                )
    
    return _database_session_store