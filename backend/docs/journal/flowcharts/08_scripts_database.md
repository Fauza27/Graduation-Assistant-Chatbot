# Flowchart: `scripts/` — Database Setup & Migration

Folder `scripts/` berisi dua file SQL yang mendefinisikan seluruh struktur database di Supabase (PostgreSQL).

---

## `supabase.sql` — Skema Database Lengkap

File ini dijalankan **sekali saat setup awal** untuk membuat semua tabel, index, dan fungsi.

### Struktur Tabel

```
TABEL: parent_documents
┌────────────────────────────────────────────┐
│ parent_id  TEXT  PRIMARY KEY               │ ← "parent-001", "parent-kkp-001"
│ title      TEXT  NOT NULL                  │ ← Judul bab/sub-bab
│ content    TEXT  NOT NULL                  │ ← Teks lengkap (untuk LLM)
│ section    TEXT  NOT NULL                  │ ← "BAB II", "Lampiran"
│ child_ids  TEXT[] DEFAULT '{}'            │ ← Array ID child yang terkait
│ created_at TIMESTAMPTZ                     │
└────────────────────────────────────────────┘

TABEL: child_documents
┌────────────────────────────────────────────┐
│ id         TEXT  PRIMARY KEY               │ ← "pi-001", "kkp-001"
│ parent_id  TEXT  FK → parent_documents     │ ← Relasi ke parent
│ title      TEXT  NOT NULL                  │
│ content    TEXT  NOT NULL                  │ ← Teks potongan kecil
│ section    TEXT  NOT NULL                  │
│ pages      TEXT[] DEFAULT '{}'            │ ← Nomor halaman sumber
│ source     TEXT  NOT NULL DEFAULT ''       │ ← Nama file PDF
│ metadata   JSONB DEFAULT '{}'             │ ← Untuk LangChain filter
│ embedding  VECTOR(2000)                    │ ← Vektor embedding (2000 dim)
│ created_at TIMESTAMPTZ                     │
└────────────────────────────────────────────┘

TABEL: user_quotas
┌────────────────────────────────────────────┐
│ user_id       TEXT     NOT NULL            │ ← Telegram user ID
│ date          TEXT     NOT NULL            │ ← Format: "YYYY-MM-DD"
│ message_count INTEGER  DEFAULT 0           │ ← Hitungan pesan hari ini
│ PRIMARY KEY (user_id, date)                │
└────────────────────────────────────────────┘

TABEL: chat_logs
┌────────────────────────────────────────────┐
│ id         BIGINT  IDENTITY PRIMARY KEY    │
│ created_at TIMESTAMPTZ                     │
│ user_id    TEXT    NOT NULL                │
│ username   TEXT                            │
│ question   TEXT    NOT NULL                │
│ answer     TEXT                            │
└────────────────────────────────────────────┘
```

### Index yang Dibuat

```
idx_child_embedding    → IVFFlat (cosine) ← untuk vector similarity search
idx_child_content_fts  → GIN tsvector     ← untuk full-text search (BM25)
idx_child_metadata     → GIN JSONB        ← untuk filter metadata
idx_child_parent_id    → B-tree           ← untuk lookup parent
idx_child_section      → B-tree           ← untuk filter section
```

### Fungsi SQL yang Didefinisikan

#### `match_documents(query_embedding, match_count)`
```
Dipakai oleh: LangChain SupabaseVectorStore (kompatibilitas)

Input:  vector query (2000 dim), jumlah hasil
Proses: Hitung cosine similarity antara query dan semua embedding child
        ORDER BY jarak vektor ASC
Output: {id, content, metadata, similarity}
```

#### `match_child_documents(query_embedding, match_threshold, match_count, filter_section)`
```
Dipakai oleh: hybrid_search.py (fallback dense-only)

Input:  vector query, threshold minimum, jumlah hasil, filter section (opsional)
Proses: Cosine similarity + filter threshold + filter section
Output: {id, parent_id, title, content, section, pages, source, metadata, similarity}
```

#### `hybrid_search(query_text, query_embedding, match_count, fts_weight, vector_weight, rrf_k, filter_section)`
```
Dipakai oleh: hybrid_search.py (metode utama)

                   query_text + query_embedding
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
        fts_results                vector_results
   Full-Text Search (BM25)      Vector Similarity
   to_tsvector('indonesian')    embedding <=> query
   websearch_to_tsquery()       ORDER BY jarak ASC
   → Hasilkan rank_ix per doc   → Hasilkan rank_ix per doc
              │                         │
              └────────────┬────────────┘
                           ▼
                     rrf_scores (FULL OUTER JOIN)
              Untuk setiap dokumen, hitung:
              fts_score   = fts_weight   × 1/(rrf_k + rank_fts)
              vector_score = vector_weight × 1/(rrf_k + rank_vec)
              combined    = fts_score + vector_score
                           │
                           ▼
              JOIN dengan child_documents
              ORDER BY combined DESC
              LIMIT match_count
                           │
              Output: {id, parent_id, content, section,
                       fts_rank, vector_rank, rrf_score}
```

> **Formula RRF:** `score = w₁/(k + rank_BM25) + w₂/(k + rank_vector)`
> Dengan bobot default: BM25=40%, Vector=60%, k=60.
> Dokumen yang muncul di kedua ranking mendapat skor lebih tinggi.

### Row Level Security (RLS)

```
Semua tabel dilindungi RLS — hanya service_role yang boleh akses:

parent_documents → SELECT, INSERT (service_role only)
child_documents  → SELECT, INSERT (service_role only)
user_quotas      → SELECT, ALL    (service_role only)
chat_logs        → SELECT, INSERT (service_role only)

Artinya: aplikasi harus menggunakan supabase_service_key,
         bukan anon_key, untuk semua operasi database.
```

---

## `supabase_migration_quota_rpc.sql` — Fungsi Kuota Harian

File ini adalah **migration** (tambahan) yang menambahkan satu fungsi RPC khusus untuk sistem kuota.

```
FUNGSI: increment_quota_if_under_limit(p_user_id, p_date, p_daily_limit)

Tujuan: Atomic check + increment kuota harian user

Alur:
       │
       ▼
  INSERT INTO user_quotas (user_id, date, message_count)
  VALUES (p_user_id, p_date, 1)
       │
  Baris sudah ada? (conflict on user_id, date)
       │
  ON CONFLICT → DO UPDATE
    SET message_count = message_count + 1
    WHERE message_count < p_daily_limit   ← Syarat kritis!
       │
  RETURNING message_count INTO v_new_count
       │
  v_new_count IS NULL?
  (terjadi jika WHERE gagal → sudah di limit)
       │
  Ya ──► RETURN FALSE  (kuota habis, tolak request)
  Tidak ► RETURN TRUE  (berhasil, request diizinkan)
```

> **Mengapa atomic?** Tanpa atomic check-and-increment, dua request bersamaan bisa sama-sama "lolos" pengecekan sebelum salah satunya mencatat. Fungsi ini mencegah race condition tersebut.

---

## Hubungan Scripts dengan Kode Python

```
scripts/supabase.sql
    │
    ├── Membuat parent_documents
    │     └── Dipakai: ingestion/embedder.py (upsert_parent_chunks)
    │                  retrieval/parent_child.py (fetch_parents)
    │                  api/health.py (cek koneksi)
    │
    ├── Membuat child_documents + embedding
    │     └── Dipakai: ingestion/embedder.py (upsert_child_chunks)
    │
    ├── Fungsi hybrid_search()
    │     └── Dipanggil: retrieval/hybrid_search.py → supabase.rpc("hybrid_search", ...)
    │
    ├── Fungsi match_child_documents()
    │     └── Dipanggil: retrieval/hybrid_search.py → supabase.rpc("match_child_documents", ...) [FALLBACK]
    │
    ├── Membuat user_quotas
    │     └── Dipakai: bot/chat_handler.py (check_and_update_quota)
    │
    └── Membuat chat_logs
          └── Dipakai: bot/chat_handler.py (log_chat_to_db)

scripts/supabase_migration_quota_rpc.sql
    │
    └── Fungsi increment_quota_if_under_limit()
          └── Dipanggil: bot/chat_handler.py → supabase.rpc("increment_quota_if_under_limit", ...)
```

---

## Urutan Setup Database

```
1. Jalankan supabase.sql di SQL Editor Supabase
   (buat tabel, index, fungsi hybrid_search, RLS)
       │
       ▼
2. Jalankan supabase_migration_quota_rpc.sql
   (tambah fungsi increment_quota_if_under_limit)
       │
       ▼
3. Jalankan python main.py --ingest
   (upload dokumen + embedding ke tabel)
       │
       ▼
4. Sistem siap digunakan!
```
