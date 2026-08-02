# Flowchart: `src/api/`

## `ai.py` — Endpoint REST Chat

```
POST /api/ai/chat
        │
        ▼
┌─────────────────────┐
│  Terima ChatRequest  │
│  query + session_id  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  chat_service(query, │
│    session_id)       │
└──────────┬──────────┘
           │
     ┌─────┴──────┐
     │ Berhasil?  │
     └─────┬──────┘
      Ya ◄─┤►─ Tidak
      │         │
      ▼         ▼
┌──────────┐  HTTP 500
│ChatResp: │
│answer    │
│num_docs  │
│sources   │
│intent    │
│confidence│
└──────────┘
```

**Peran file:** Menerima request HTTP dari frontend/client, meneruskan ke `ai_services.py`, mengembalikan respons terstruktur.

---

## `health.py` — Health Check Endpoints

```
GET /health/            GET /health/detailed     GET /health/readiness
       │                       │                        │
       ▼                       ▼                        ▼
 Return basic:         Cek OpenAI API           Cek OpenAI API
 status, version,      Cek Supabase DB          Cek Supabase DB
 uptime, env           Cek Telegram Bot              │
                       Get session stats    ┌────────┴────────┐
                              │            OK           Error
                              ▼             │               │
                       Tentukan status    Resp           HTTP 503
                       healthy/degraded  "ready"
```

**Peran file:** Monitoring kesehatan sistem. Dipakai deployment checker (Kubernetes readiness probe).
