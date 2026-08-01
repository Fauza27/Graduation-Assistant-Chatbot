# Panduan Deployment — Development hingga Production

---

## Mode Development (Lokal)

### Cara Menjalankan
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Setup .env (copy dari .env.example)
cp .env.example .env
# Edit .env, isi semua variabel wajib

# 3. Setup database (jalankan sekali)
# Buka Supabase Dashboard → SQL Editor
# Jalankan: scripts/supabase.sql
# Jalankan: scripts/supabase_migration_quota_rpc.sql

# 4. Ingest data (jalankan sekali, atau saat ada data baru)
python main.py --ingest --dataset both

# 5. Jalankan server
python main.py
# Server berjalan di http://localhost:8000
# Docs tersedia di http://localhost:8000/docs
```

### Mode-Mode yang Tersedia
```bash
python main.py                          # FastAPI server (REST + Telegram webhook)
python main.py --cli                    # Chat interaktif di terminal
python main.py --question "Apa KKP?"   # Tanya satu pertanyaan
python main.py --ingest --dataset both # Upload semua data ke Supabase
python main.py --ingest --dataset pi   # Upload hanya data PI
python main.py --ingest --dataset kkp  # Upload hanya data KKP
python main.py --evaluate              # Evaluasi RAGAS dengan ground truth
python main.py --evaluate-no-gt        # Evaluasi RAGAS tanpa ground truth
python main.py --debug --question "..."# Mode debug dengan log detail
```

---

## Mode Production (Docker)

### Dockerfile — Cara Build Image
```
FROM python:3.11-slim
  │
  ▼
WORKDIR /app
  │
  ▼
COPY requirements.txt
pip install --no-cache-dir -r requirements.txt
  │
  ▼
COPY . .
  │
  ▼
EXPOSE 8000
  │
  ▼
CMD ["python", "main.py"]
  (Jalankan uvicorn via main.py)
```

### docker-compose.yml — Cara Jalankan
```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPEN_API_KEY=${OPEN_API_KEY}
      - SUPABASE_URL=${SUPABASE_URL}
      ...
    restart: unless-stopped
```

```bash
# Build dan jalankan
docker-compose up -d

# Lihat log
docker-compose logs -f

# Stop
docker-compose down
```

---

## Alur Startup Server

```
python main.py (tanpa argumen)
       │
       ▼
setup_logger()             ← setup format log
       │
       ▼
get_settings()             ← load & validasi .env
       │
  Gagal? ──► sys.exit(1)
       │
       ▼
uvicorn.run("application:create_app", ...)
       │
       ▼
FastAPI create_app()
  ├─ Buat instance FastAPI
  ├─ Setup rate limiter (SlowAPI 100/menit)
  ├─ Register middleware (CORS, SlowAPI)
  └─ Register router (/api/ai/chat, /health, /)
       │
       ▼
lifespan() dipanggil
  │
  ├─ TELEGRAM_WEBHOOK_URL ada?
  │    Ya: create_bot() → initialize → set_webhook → start
  │    Tidak: skip (bot tidak aktif)
  │
  ▼
Server SIAP menerima request
```

---

## Perbedaan Development vs Production

| Aspek | Development | Production |
|-------|------------|-----------|
| `ENVIRONMENT` | `development` | `production` |
| Hot reload | ✅ Aktif | ❌ Mati |
| `/docs` Swagger UI | ✅ Tersedia | ❌ Disembunyikan |
| HSTS header | ❌ Tidak ada | ✅ Aktif |
| Webhook secret | Opsional | **Wajib** (min 16 char) |
| Log level | INFO/DEBUG | INFO |
| Bot mode | Polling (opsional) | Webhook |

---

## Health Check Endpoints

Setelah server jalan, bisa dicek dengan:

```bash
# Cek dasar
curl http://localhost:8000/health
# Response: {"status":"healthy","app":"Chatbot KKP/PI","version":"1.0.0",...}

# Cek detail (OpenAI + Supabase connectivity)
curl http://localhost:8000/health/detailed

# Cek readiness (Kubernetes)
curl http://localhost:8000/health/readiness
# Response 200: {"status":"ready",...}
# Response 503: jika OpenAI atau Supabase tidak bisa diakses

# Cek liveness (Kubernetes)
curl http://localhost:8000/health/liveness
```

---

## Test Manual API

```bash
# Kirim pertanyaan via REST API
curl -X POST http://localhost:8000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Apa syarat mengambil KKP?",
    "session_id": "test-session-001"
  }'

# Response:
{
  "answer": "Berdasarkan BAB II...",
  "num_docs": 8,
  "session_id": "test-session-001",
  "sources": [...],
  "intent": "needs_retrieval",
  "confidence": 0.99,
  "reasoning": "First question needs retrieval"
}
```
