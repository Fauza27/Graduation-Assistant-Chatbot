# Configuration Reference

Configuration is defined by `config/settings.py` and loaded from `.env`.
Never commit `.env`, API keys, database service keys, or JWT secrets.

| Group | Important settings | Purpose |
| --- | --- | --- |
| Application | `ENVIRONMENT`, `CORS_ALLOWED_ORIGINS` | Runtime mode and allowed browser origins. |
| OpenAI | `OPEN_API_KEY`, `LLM_MODEL`, `EMBEDDING_MODEL` | Generation and embedding providers. |
| Supabase | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Persistent data access. |
| Retrieval | `RETRIEVAL_TOP_K`, `RERANK_TOP_N`, `BM25_WEIGHT`, `DENSE_WEIGHT` | Candidate count and hybrid-ranking behavior. |
| Memory | `MEMORY_MAX_HISTORY_TOKENS`, `MEMORY_MIN_RECENT_TURNS`, `MEMORY_SUMMARY_MAX_TOKENS` | Two-level conversation memory budget. |
| Sessions | `USE_DATABASE_SESSIONS`, `MAX_ACTIVE_SESSIONS` | Durable sessions and in-memory fallback capacity. |
| Evaluation | `EVALUATION_*` | Document scanning, evidence selection, and batch size. |
| Security | `JWT_SECRET_KEY`, `GOOGLE_CLIENT_ID`, `TRUSTED_PROXIES` | Authentication and trusted network headers. |
| Observability | `ENABLE_REQUEST_METRICS`, `OTEL_*` | Metrics persistence and distributed tracing. |

In production, settings validation requires a unique JWT secret of at least 32
bytes and enables refresh tokens. Keep the development and production values
separate.
