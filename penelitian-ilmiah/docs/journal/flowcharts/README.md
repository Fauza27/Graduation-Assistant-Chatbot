# Index Dokumentasi — Chatbot RAG KKP/PI

Panduan lengkap untuk memahami sistem chatbot ini dari nol hingga mendalam.

---

## 📚 Daftar Dokumen

### Pemahaman Dasar (Mulai di Sini)

| File | Isi | Waktu Baca |
|------|-----|-----------|
| [00_overview.md](./00_overview.md) | Peta besar sistem, dependency antar file, ringkasan per folder | 10 menit |
| [12_glossary.md](./12_glossary.md) | Penjelasan semua istilah teknis (RAG, BM25, RRF, dll.) | 15 menit |

### Memahami Alur Nyata

| File | Isi | Waktu Baca |
|------|-----|-----------|
| [09_trace_nyata.md](./09_trace_nyata.md) | Step-by-step apa yang terjadi saat user bertanya "Apa syarat KKP?" | 15 menit |
| [10_sequence_diagram.md](./10_sequence_diagram.md) | Urutan pemanggilan fungsi (kronologis) untuk semua skenario | 10 menit |
| [11_transformasi_data.md](./11_transformasi_data.md) | Bentuk data di setiap tahap pipeline (input → output) | 10 menit |

### Memahami Keputusan Sistem

| File | Isi | Waktu Baca |
|------|-----|-----------|
| [15_perbandingan_intent.md](./15_perbandingan_intent.md) | Kapan CONVERSATIONAL vs CLARIFICATION vs NEEDS_RETRIEVAL dipilih | 10 menit |
| [13_error_fallback.md](./13_error_fallback.md) | Apa yang terjadi saat ada error, dan fallback-nya | 10 menit |

### Memahami Per Modul (Detail)

| File | Modul yang Dibahas | Waktu Baca |
|------|-------------------|-----------|
| [01_api.md](./01_api.md) | `src/api/` — REST endpoints | 5 menit |
| [02_services.md](./02_services.md) | `src/services/` — Otak utama chatbot | 10 menit |
| [03_generation.md](./03_generation.md) | `src/generation/` — Memory, Chain, Intent Classifier | 20 menit |
| [04_retrieval.md](./04_retrieval.md) | `src/retrieval/` — Pipeline pencarian dokumen | 20 menit |
| [05_ingestion.md](./05_ingestion.md) | `src/ingestion/` — Upload data ke database | 10 menit |
| [06_bot.md](./06_bot.md) | `src/bot/` — Integrasi Telegram | 10 menit |
| [07_middleware.md](./07_middleware.md) | `src/middleware/` — Security & monitoring | 10 menit |

### Referensi Teknis

| File | Isi | Waktu Baca |
|------|-----|-----------|
| [08_scripts_database.md](./08_scripts_database.md) | Skema database, index, fungsi SQL | 15 menit |
| [14_konfigurasi_env.md](./14_konfigurasi_env.md) | Semua variabel `.env` dan dampaknya | 10 menit |
| [16_struktur_data_json.md](./16_struktur_data_json.md) | Format file JSON input ingestion | 10 menit |
| [17_deployment.md](./17_deployment.md) | Cara jalankan: development, Docker, production | 10 menit |

---

## 🗺️ Peta Alur Pertanyaan User

```
User (Telegram / REST API)
         │
         ▼
[Middleware] Rate Limit + CORS
         │
         ▼
[api/ai.py atau bot/chat_handler.py]
         │
         ▼
[ai_services.py] Kelola sesi + routing
         │
    ┌────┴───────────────┐
    ▼                    ▼                    ▼
CONVERSATIONAL     CLARIFICATION       NEEDS_RETRIEVAL
    │                    │                    │
    ▼                    ▼                    ▼
[chain.py]         [chain.py]        [retrieval/pipeline.py]
invoke_conv        invoke_clarif      self_query → expand
                                      → embed → hybrid_search
                                      → parent_child
                                      → reranker
                                           │
                                           ▼
                                      [chain.py]
                                    invoke_with_history
                                           │
                                           ▼
                                      OpenAI LLM
                                           │
                                           ▼
                                    Jawaban ke User
```

---

## 🏃 Urutan Belajar yang Disarankan

### Untuk Presentasi / Sidang (2-3 jam)
1. `12_glossary.md` — pahami istilah dulu
2. `00_overview.md` — gambaran besar
3. `09_trace_nyata.md` — ikuti satu pertanyaan dari awal sampai akhir
4. `15_perbandingan_intent.md` — pahami logika keputusan intent

### Untuk Pemahaman Mendalam (1 hari)
1. Baca semua file urut dari `00` sampai `17`
2. Sambil baca, buka file kode Python yang bersesuaian
3. Coba jalankan `python main.py --cli` dan tanya beberapa pertanyaan

### Untuk Interview / Wawancara Kerja
Fokus pada:
- `09_trace_nyata.md` → bisa ceritakan alur sistem
- `11_transformasi_data.md` → bisa tunjukkan transformasi data
- `12_glossary.md` → bisa jelaskan istilah teknis
- `13_error_fallback.md` → bisa jelaskan ketangguhan sistem
