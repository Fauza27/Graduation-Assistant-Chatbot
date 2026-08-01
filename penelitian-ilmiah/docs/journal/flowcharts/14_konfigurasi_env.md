# Panduan Konfigurasi `.env` & Settings

Penjelasan setiap variabel konfigurasi dan dampaknya ke sistem.

---

## Variabel Wajib (Sistem Tidak Bisa Jalan Tanpa Ini)

| Variabel | Contoh Nilai | Penjelasan |
|----------|-------------|-----------|
| `OPEN_API_KEY` | `sk-proj-...` | API Key OpenAI. Dipakai untuk LLM (GPT-4o-mini) dan embedding. |
| `SUPABASE_URL` | `https://xxx.supabase.co` | URL project Supabase. |
| `SUPABASE_SERVICE_KEY` | `eyJhbG...` | Service role key Supabase. Harus service_role, bukan anon. |
| `TELEGRAM_BOT_TOKEN` | `123456:ABC...` | Token bot Telegram dari @BotFather. |

---

## Variabel Model AI

| Variabel | Default | Dampak Jika Diubah |
|----------|---------|-------------------|
| `LLM_MODEL` | `gpt-4o-mini` | Ganti ke `gpt-4o` untuk jawaban lebih baik (lebih mahal) |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | Jangan diubah kecuali mau re-ingest semua data |

> ⚠️ Jika `EMBEDDING_MODEL` diubah, semua data di `child_documents` harus di-embed ulang karena dimensi vektor berubah.

---

## Variabel Retrieval (Tuning Kualitas Pencarian)

| Variabel | Default | Penjelasan |
|----------|---------|-----------|
| `RETRIEVAL_TOP_K` | `30` | Berapa child chunk yang diambil dari hybrid search sebelum reranking. Lebih besar = recall lebih tinggi tapi lebih lambat. |
| `RERANK_TOP_N` | `8` | Berapa parent doc yang dikirim ke LLM setelah reranking. Lebih besar = konteks lebih banyak tapi lebih mahal token. |
| `BM25_WEIGHT` | `0.4` | Bobot pencarian keyword (BM25). Harus `BM25_WEIGHT + DENSE_WEIGHT = 1.0`. |
| `DENSE_WEIGHT` | `0.6` | Bobot pencarian semantik (vector). |
| `CROSS_ENCODER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Model HuggingFace untuk reranking. |

**Panduan tuning:**
```
Pertanyaan spesifik (istilah teknis) → naikkan BM25_WEIGHT
Pertanyaan umum (parafrase berbeda) → naikkan DENSE_WEIGHT
Jawaban kurang relevan → naikkan RETRIEVAL_TOP_K
Konteks LLM terlalu panjang/mahal → turunkan RERANK_TOP_N
```

---

## Variabel Database

| Variabel | Default | Keterangan |
|----------|---------|-----------|
| `TABLE_PARENT_CHUNKS` | `parent_documents` | Nama tabel parent di Supabase |
| `TABLE_CHILD_CHUNKS` | `child_documents` | Nama tabel child di Supabase |
| `TABLE_USER_QUOTAS` | `user_quotas` | Nama tabel kuota harian |
| `TABLE_CHAT_LOGS` | `chat_logs` | Nama tabel log percakapan |

---

## Variabel Session & Memory

| Variabel | Default | Penjelasan |
|----------|---------|-----------|
| `MAX_ACTIVE_SESSIONS` | `1000` | Maks sesi aktif di memory. Jika penuh, sesi paling lama dihapus (LRU). |
| `SESSION_CLEANUP_INTERVAL` | `3600` (1 jam) | Sesi yang tidak aktif selama ini otomatis dihapus. |

---

## Variabel Rate Limiting

| Variabel | Default | Penjelasan |
|----------|---------|-----------|
| `RATE_LIMIT_REQUESTS` | `13` | Maks pertanyaan per user per hari (Telegram). |
| `RATE_LIMIT_WINDOW` | `86400` (1 hari) | Jendela waktu untuk rate limit (detik). |
| `MAX_CONCURRENT_REQUESTS` | `10` | Maks request yang diproses bersamaan. |

---

## Variabel Telegram Webhook (Untuk Production)

| Variabel | Default | Penjelasan |
|----------|---------|-----------|
| `TELEGRAM_WEBHOOK_URL` | `""` | URL publik server (contoh: `https://myapp.railway.app`). Kosong = bot tidak aktif. |
| `TELEGRAM_WEBHOOK_PATH` | `/api/telegram/webhook` | Path endpoint webhook. |
| `TELEGRAM_WEBHOOK_SECRET` | `""` | Secret token untuk verifikasi request dari Telegram. Wajib di production (min. 16 karakter). |

---

## Variabel Environment

| Variabel | Nilai Valid | Dampak |
|----------|------------|--------|
| `ENVIRONMENT` | `development` | Hot reload aktif, docs tersedia di `/docs` |
| `ENVIRONMENT` | `staging` | Hot reload mati, docs tersedia |
| `ENVIRONMENT` | `production` | Hot reload mati, docs disembunyikan, HSTS aktif |
| `DEBUG` | `false` | Log level INFO |
| `DEBUG` | `true` | Log level DEBUG (lebih verbose) |

---

## Variabel OpenAI Rate Limiting

| Variabel | Default | Penjelasan |
|----------|---------|-----------|
| `OPENAI_MAX_RETRIES` | `3` | Berapa kali retry jika OpenAI error |
| `OPENAI_TIMEOUT` | `60` | Timeout tiap request OpenAI (detik) |

---

## Variabel Opsional

| Variabel | Default | Penjelasan |
|----------|---------|-----------|
| `HF_TOKEN` | `None` | Token HuggingFace. Dibutuhkan jika cross-encoder model bersifat private. |
| `LOG_LEVEL` | `INFO` | Level log: DEBUG, INFO, WARNING, ERROR |
| `LOG_FILE` | `None` | Path file log. Jika None, log hanya ke stderr. |
| `PORT` | `8000` | Port server (dibaca dari env, bukan pydantic settings) |

---

## Contoh `.env` Lengkap

```env
# === WAJIB ===
OPEN_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxx
SUPABASE_URL=https://abcdefgh.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
TELEGRAM_BOT_TOKEN=1234567890:AAFxxxxxxxxxxxxxxxxxx

# === ENVIRONMENT ===
ENVIRONMENT=development
DEBUG=false

# === MODEL (optional, sudah ada default) ===
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-large

# === RETRIEVAL TUNING (optional) ===
RETRIEVAL_TOP_K=30
RERANK_TOP_N=8
BM25_WEIGHT=0.4
DENSE_WEIGHT=0.6

# === SESSION (optional) ===
MAX_ACTIVE_SESSIONS=1000
SESSION_CLEANUP_INTERVAL=3600

# === RATE LIMIT (optional) ===
RATE_LIMIT_REQUESTS=13

# === PRODUCTION ONLY ===
# TELEGRAM_WEBHOOK_URL=https://myapp.railway.app
# TELEGRAM_WEBHOOK_SECRET=my-super-secret-token-16chars
```

---

## Validasi Otomatis Settings

`config/settings.py` secara otomatis memvalidasi:

```
✓ BM25_WEIGHT + DENSE_WEIGHT harus = 1.0 (toleransi 0.001)
✓ OPEN_API_KEY tidak boleh kosong
✓ SUPABASE_SERVICE_KEY tidak boleh kosong
✓ TELEGRAM_BOT_TOKEN tidak boleh kosong
✓ Di production + webhook URL → WEBHOOK_SECRET min 16 karakter
✗ Jika gagal → ValueError saat startup, program berhenti
```
