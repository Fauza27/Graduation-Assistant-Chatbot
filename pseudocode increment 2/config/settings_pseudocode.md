# Pseudocode untuk `config/settings.py`

```markdown
ALGORITMA KONFIGURASI SISTEM (config/settings.py)

1. IMPOR PUSTAKA
   - pydantic dan pydantic_settings (untuk memvalidasi dan memuat tipe data otomatis dari .env)

2. FUNGSI _find_env_file()
   - Cari file konfigurasi ".env".
   - Mulai dari direktori saat ini.
   - ULANGI hingga 5 level folder ke atas:
     - Jika file ".env" ditemukan di folder tersebut, kembalikan path-nya.
     - Mundur 1 level direktori.
   - KEMBALIKAN fallback ".env" jika tidak ditemukan secara eksplisit.

3. KELAS Settings (mewarisi BaseSettings)
   - Konfigurasi ini otomatis memuat variabel dari file `.env`.
   
   - VARIABEL APLIKASI UTAMA:
     - APP_NAME (Default: "Chatbot KKP/PI Assistant")
     - VERSION
     - ENVIRONMENT ("development", "staging", "production")
     - DEBUG mode
   
   - KONFIGURASI OPENAI (Wajib Diisi):
     - open_api_key, llm_model, embedding_model
     - Rate limit dan toleransi timeout OpenAI (retry max 3 kali).
     
   - KONFIGURASI DATABASE SUPABASE (Wajib Diisi):
     - supabase_url, supabase_service_key
     - Nama-nama tabel database (parent_documents, child_documents, user_quotas, chat_logs, conversation_sessions)
     
   - PENGATURAN RETRIEVAL (Pencarian RAG):
     - retrieval_top_k: jumlah potongan dokumen maksimal dicari (default 30)
     - rerank_top_n: jumlah dokumen final setelah disaring (default 8)
     - max_parent_for_rerank: jumlah maksimal parent dikirim ke reranker (default 8)
     - min_parent_for_rerank: syarat minimal parent agar reranker jalan (default 3)
     - rerank_min_top_score: skor top minimal untuk melanjutkan (default 0.0)
     - rerank_relative_gap: gap skor dari top score untuk menjaga dokumen (default 2.5)
     - bm25_weight: bobot pencarian teks BM25 (default 0.4)
     - dense_weight: bobot pencarian vektor semantic (default 0.6)
     
   - PENGATURAN MODEL LOKAL:
     - cross_encoder_model (untuk reranking dokumen lokal)
     
   - PENGATURAN TELEGRAM BOT:
     - TELEGRAM_BOT_TOKEN
     - Webhook URL, Secret Token, Path Webhook
     
   - PENGATURAN RATE LIMIT & MEMORI:
     - Batas request per hari (RATE_LIMIT_REQUESTS).
     - Maksimal sesi chat aktif, interval pembersihan sesi lama.
     - Penggunaan Database Sessions (USE_DATABASE_SESSIONS: True).
     - MAX_HISTORY_TURNS: Batas jumlah giliran histori yang dikirim ke LLM (default 3).

4. METODE VALIDATOR DATA:
   - FUNGSI validate_weights_sum:
     - Pastikan bahwa `bm25_weight` + `dense_weight` sama dengan 1.0. 
     - JIKA hasil jumlah tidak 1.0, lemparkan error "must equal 1.0".
   - FUNGSI validate_webhook_secret:
     - JIKA environment = "production" DAN ada webhook URL:
       - Pastikan token rahasia ada dan panjangnya minimal 16 karakter.
       - Jika tidak, lemparkan error keamanan.
   - FUNGSI validate_required_secrets:
     - Cek OpenAI key, Supabase key, dan Telegram bot token agar tidak boleh bernilai string kosong.

5. FUNGSI PEMBANTU (Helper Methods):
   - get_openai_config(): Mengembalikan dictionary konfigurasi khusus API OpenAI.
   - get_supabase_config(): Mengembalikan dictionary konfigurasi database Supabase.
   - is_production(): Cek apakah environment sedang production.
   - is_development(): Cek apakah environment sedang development.

6. FUNGSI get_settings()
   - Menggunakan `@lru_cache` (pola Singleton).
   - Memastikan kelas `Settings` hanya di-load 1 kali dari memori selama aplikasi berjalan.
   - KEMBALIKAN instance `Settings`.
```
