# Ringkasan Sistem: Hubungan Antar File `src/`

## Peta Alur Pertanyaan User (Query Flow)

```
USER (REST API atau Telegram)
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                     LAYER TRANSPORT                          │
│                                                             │
│  REST: src/api/ai.py          TELEGRAM: src/bot/            │
│   POST /api/ai/chat            handlers/chat_handler.py     │
│         │                              │                    │
│         │    [Cek kuota harian]        │                    │
│         └──────────────┬──────────────┘                    │
└──────────────────────── │ ────────────────────────────────── ┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  LAYER ORCHESTRATION                         │
│                                                             │
│              src/services/ai_services.py                    │
│                  chat(query, session_id)                    │
│                                                             │
│   Kelola sesi ──► Tambah ke memory ──► Klasifikasi intent   │
└──────────────────────── │ ────────────────────────────────── ┘
                          │
               ┌──────────┼──────────────┐
               ▼          ▼              ▼
         CONVERSATIONAL  CLARIF.    NEEDS_RETRIEVAL
               │          │              │
               ▼          ▼              ▼
┌──────────────────────────────────────────────────────────── ┐
│                   LAYER GENERATION                           │
│                                                             │
│              src/generation/chain.py (RAGChain)             │
│                                                             │
│  invoke_conversational  invoke_clarification  invoke_with_  │
│  (tanpa retrieval)      (konteks lama)        history()     │
│         │                    │                    │ ▲       │
└──────── │ ────────────────── │ ──────────────── │ │ ─────── ┘
          │                    │                  │ │
          │             (jika konteks             │ │
          │              tidak relevan)           │ │
          │                    │                  ▼ │
          │                    └──────────────────  │
          │                          RETRIEVAL      │
          │   ┌─────────────────────────────────────┘
          │   │
          │   ▼
          │  ┌─────────────────────────────────────────────────┐
          │  │              LAYER RETRIEVAL                    │
          │  │                                                 │
          │  │  src/retrieval/pipeline.py (run_retrieval)      │
          │  │         │                                       │
          │  │  self_query.py ──► Deteksi filter PI/KKP/bab   │
          │  │  query_expansion.py ──► Ekspansi akronim        │
          │  │  hybrid_search.py ──► BM25 + Vector Search      │
          │  │  parent_child.py ──► Fetch parent docs          │
          │  │  reranker.py ──► Cross-encoder scoring          │
          │  │  source_utils.py ──► Label PI vs KKP           │
          │  └─────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                         │
│                                                             │
│   OpenAI API                    Supabase (PostgreSQL)       │
│   ├─ ChatOpenAI (LLM)           ├─ parent_documents         │
│   └─ OpenAIEmbeddings           ├─ child_documents          │
│      (text-embedding-3-large)   ├─ user_quotas              │
│                                 └─ chat_logs                │
└─────────────────────────────────────────────────────────────┘
```

---

## Siapa Memanggil Siapa?

| File | Dipanggil oleh | Memanggil |
|------|---------------|-----------|
| `api/ai.py` | FastAPI router | `services/ai_services.py` |
| `api/health.py` | FastAPI router | `services/ai_services.py`, `config/settings.py` |
| `services/ai_services.py` | `api/ai.py`, `bot/chat_handler.py` | `generation/memory.py`, `generation/chain.py`, `generation/intent_classifier/`, `retrieval/pipeline.py` |
| `generation/memory.py` | `services/ai_services.py`, `intent_classifier/` | *(tidak ada)* |
| `generation/chain.py` | `services/ai_services.py` | `retrieval/pipeline.py`, `retrieval/source_utils.py` |
| `intent_classifier/classifier.py` | `services/ai_services.py` | `detectors.py`, `memory.py`, `reformulator.py` |
| `intent_classifier/detectors.py` | `classifier.py` | `memory.py`, `constants.py` |
| `intent_classifier/reformulator.py` | `classifier.py` (via `__init__`) | `memory.py` |
| `retrieval/pipeline.py` | `services/ai_services.py`, `generation/chain.py` | `self_query.py`, `hybrid_search.py`, `parent_child.py`, `reranker.py` |
| `retrieval/hybrid_search.py` | `retrieval/pipeline.py` | `query_expansion.py` |
| `retrieval/self_query.py` | `retrieval/pipeline.py` | *(loads YAML)* |
| `retrieval/parent_child.py` | `retrieval/pipeline.py` | *(Supabase)* |
| `retrieval/reranker.py` | `retrieval/pipeline.py` | *(HuggingFace CrossEncoder)* |
| `retrieval/source_utils.py` | `generation/chain.py`, `bot/chat_handler.py` | *(tidak ada)* |
| `ingestion/embedder.py` | `main.py` | `ingestion/loader.py` |
| `ingestion/loader.py` | `ingestion/embedder.py` | *(tidak ada)* |
| `bot/application.py` | `application.py` | `bot/handlers/chat_handler.py` |
| `bot/handlers/chat_handler.py` | `bot/application.py` | `services/ai_services.py`, `retrieval/source_utils.py` |
| `bot/messages.py` | `bot/handlers/chat_handler.py`, `bot/application.py` | *(tidak ada)* |
| `middleware/security.py` | `application.py` | `config/settings.py` |
| `middleware/monitoring.py` | `application.py` | *(tidak ada)* |

---

## Ringkasan Per Folder

| Folder | Fungsi Utama |
|--------|-------------|
| `src/api/` | Endpoint HTTP REST (chat & health check) |
| `src/services/` | Orchestrator utama: sesi + routing intent |
| `src/generation/` | Memori percakapan + klasifikasi intent + pembuatan jawaban LLM |
| `src/retrieval/` | Pipeline pencarian dokumen: filter → search → fetch → rerank |
| `src/ingestion/` | Pipeline satu kali: load PDF chunks → embed → upload ke Supabase |
| `src/bot/` | Integrasi Telegram Bot: handler pesan + kuota + format pesan |
| `src/middleware/` | Rate limiting, keamanan header, monitoring performa |
