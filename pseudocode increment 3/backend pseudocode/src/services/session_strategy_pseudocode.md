# Pseudocode untuk `src/services/session_strategy.py` (NEW STRATEGY PATTERN)

```markdown
ALGORITMA SESSION STORAGE STRATEGY PATTERN (session_strategy.py)

1. IMPOR PUSTAKA
   - abc (Abstract Base Class dan abstractmethod)
   - typing (untuk Dict, Any, Optional)
   - time, threading.Lock (untuk legacy strategy)
   - loguru.logger, src.generation.memory.ConversationMemory
   - config.settings

2. ABSTRACT CLASS SessionStore(ABC)
   - @abstractmethod load_memory(session_id, mahasiswa_id=None) -> ConversationMemory
   - @abstractmethod save_memory(session_id, memory, channel="telegram", mahasiswa_id=None) -> None
   - @abstractmethod delete_session(session_id) -> bool
   - @abstractmethod get_session_stats() -> Dict[str, Any]
   - @abstractmethod cleanup_idle_sessions() -> int
   
   TUJUAN: Interface contract untuk semua session storage implementations

3. CLASS DatabaseSessionStrategy(SessionStore)
   - KONSTRUKTOR __init__():
     - Import get_session_store dari session_store.py
     - self._store = get_session_store()
     - Log "Using database-backed session storage strategy"
   
   - IMPLEMENTASI semua abstract methods:
     - load_memory(): Delegate ke self._store.load_memory()
     - save_memory(): Delegate ke self._store.save_memory()
     - delete_session(): Delegate ke self._store.delete_session()
     - get_session_stats(): Delegate ke self._store.get_session_stats()
     - cleanup_idle_sessions(): Delegate ke self._store.cleanup_idle_sessions()
   
   WRAPPER pattern untuk existing DatabaseSessionStore

4. CLASS LegacyInMemorySessionStrategy(SessionStore)
   - KONSTRUKTOR __init__():
     - self._session_store: dict[session_id -> (memory, timestamp)]
     - self._session_lock = Lock() untuk thread safety
     - self._settings = get_settings()
     - Log "Using legacy in-memory session storage strategy"
   
   - load_memory(session_id, mahasiswa_id=None):
     - Lock context untuk thread safety
     - Evict idle sessions dengan _evict_idle_sessions()
     - Cek existing session, update timestamp jika ada
     - Buat ConversationMemory baru jika tidak ada
     - Evict LRU jika storage full dengan _evict_lru_if_full()
     - KEMBALIKAN memory instance
   
   - save_memory(): Update timestamp di in-memory store
   - delete_session(): Hapus dari dictionary dengan lock
   - get_session_stats(): Return dict dengan active_sessions, total_turns
   - cleanup_idle_sessions(): Manual eviction dengan timestamp check
   
   - HELPER METHODS:
     - _evict_idle_sessions(now): Hapus session > SESSION_CLEANUP_INTERVAL
     - _evict_lru_if_full(): Hapus oldest sessions jika > MAX_ACTIVE_SESSIONS

5. FACTORY FUNCTION create_session_store() -> SessionStore
   - settings = get_settings()
   - IF settings.USE_DATABASE_SESSIONS:
     - TRY: return DatabaseSessionStrategy()
     - EXCEPT: Log error, fallback ke legacy
   - RETURN LegacyInMemorySessionStrategy()
   
   SINGLE POINT untuk strategy selection - dipanggil ONCE saat startup

6. BENEFITS OF STRATEGY PATTERN:
   - ✅ ELIMINASI 6+ repeated if/else branching di ai_services.py
   - ✅ CLEANER ARCHITECTURE: Single strategy interface
   - ✅ EXTENSIBILITY: Mudah tambah Redis/other storage types
   - ✅ TESTABILITY: Mock strategy untuk unit testing
   - ✅ PERFORMANCE: Strategy chosen once vs checked every call
   - ✅ SEPARATION OF CONCERNS: Logic terpisah per implementation

7. MIGRATION FROM OLD ARCHITECTURE:
   - BEFORE: if settings.USE_DATABASE_SESSIONS everywhere
   - AFTER: _session_store_strategy.method_name()
   - RESULT: Cleaner, more maintainable code structure
```