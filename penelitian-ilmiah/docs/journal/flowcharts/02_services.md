# Flowchart: `src/services/`

## `ai_services.py` — Otak Utama Chatbot

File ini adalah **orchestrator** utama: mengelola sesi user dan mengarahkan setiap pesan ke jalur yang benar.

```
chat(query, session_id)
        │
        ├─ Query kosong? ──► Return error "empty_query"
        ├─ No session_id? ──► Return error "missing_session_id"
        │
        ▼
get_or_create_memory(session_id)
  ├─ USE_DATABASE_SESSIONS? 
  │   ├─ YES → DatabaseSessionStore.load_memory()
  │   │   ├─ Check LRU cache first (hot path)
  │   │   ├─ Cache miss → Load from Supabase
  │   │   └─ Update last_access timestamp
  │   └─ NO → Legacy in-memory store
  │       ├─ TTL cleanup: buang sesi idle > SESSION_CLEANUP_INTERVAL
  │       ├─ Jika sesi ada → perbarui timestamp
  │       └─ Jika baru → buat ConversationMemory, cek LRU cap
        │
        ▼
memory.add_user_turn(question)
        │
        ▼
_classifier.classify(question, memory)
        │
   ┌────┴──────────────────────┐
   ▼                           ▼                         ▼
CONVERSATIONAL          CLARIFICATION            NEEDS_RETRIEVAL
   │                           │                         │
invoke_conversational    invoke_clarification    _handle_retrieval()
(tanpa retrieval)        (konteks lama)               │
   │                           │               reformulate_query()
   │                           │               run_retrieval()
   │                           │               invoke_with_history()
   └───────────────────────────┴─────────────────────────┘
                               │
                               ▼
                   memory.add_assistant_turn()
                               │
                               ▼
                   _save_memory_if_needed()
                   ├─ Database sessions → save to Supabase
                   └─ In-memory sessions → no action needed
                               │
                               ▼
              Return: {answer, num_docs, sources,
                       intent, confidence, reasoning}
```

### Manajemen Sesi (Session Store)

#### **Database-Backed Sessions (Default)**

```
DatabaseSessionStore
├─ Hot LRU Cache (in-memory, ~50 sessions)
│   ├─ Cache hit → return immediately (0ms)
│   └─ Cache miss → load from database
├─ Supabase Storage
│   ├─ Table: conversation_sessions
│   ├─ Columns: session_id, turns (JSONB), last_access, created_at
│   └─ Auto cleanup via cleanup_idle_sessions() RPC
└─ Write-through strategy
    ├─ Every chat → save to database
    └─ Update cache simultaneously
```

**Keuntungan:**
- ✅ **Persistent**: Session survive server restart
- ✅ **Multi-server**: Shared state across load balancer
- ✅ **Scalable**: Database handles large session counts
- ✅ **Observable**: Statistics & monitoring via SQL

#### **Legacy In-Memory Sessions (Fallback)**

```
_legacy_session_store = { session_id: (ConversationMemory, last_access_ts) }

Setiap akses:
  ├─ _evict_idle_sessions()  → hapus yang idle > TTL
  └─ _evict_lru_if_full()    → hapus terlama jika > MAX_ACTIVE_SESSIONS
```

**Kapan digunakan:**
- Database connection gagal
- `USE_DATABASE_SESSIONS=false` di .env
- Fallback otomatis jika ada error

### Konfigurasi Session Storage

```bash
# .env configuration
USE_DATABASE_SESSIONS=true              # Enable database sessions
TABLE_CONVERSATION_SESSIONS=conversation_sessions
MAX_ACTIVE_SESSIONS=1000               # Cache size untuk database mode
SESSION_CLEANUP_INTERVAL=3600          # TTL cleanup (seconds)
```

### Migration & Deployment

1. **Zero-downtime migration**: Deploy dengan feature flag
2. **Automatic fallback**: Jika database error, fallback ke in-memory
3. **Monitoring**: Session statistics via `get_session_stats()`
4. **Cleanup**: Automatic TTL cleanup via database RPC
