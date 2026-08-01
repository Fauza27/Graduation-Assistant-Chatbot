# Flowchart: `src/ingestion/`

## `loader.py` — Loader & Validator Data JSON

Membaca file JSON hasil ekstraksi PDF dan memvalidasi strukturnya sebelum diproses.

```
load_child_chunks(path)
       │
  File ada? ──No──► FileNotFoundError
       │Yes
       ▼
  JSON array? ──No──► ValueError
       │Yes
       ▼
  Cek setiap chunk punya field:
    {"id", "title", "content", "section"}
  ──Ada yang kurang?──► ValueError: missing fields
       │OK
       ▼
  Ada ID duplikat? ──Yes──► ValueError: duplicate IDs
       │No
Return list[dict] child chunks

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

load_parent_chunks(path)
  Sama seperti di atas, tapi field wajib:
  {"parent_id", "title", "content", "section", "child_ids"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

validate_parent_child_links(parents, children)
       │
       ▼
  Buat child_ids_set dari semua children
       │
       ▼
  Setiap parent.child_ids harus ada di child_ids_set
  ──Ada yang tidak ada?──► ValueError: referensi tidak valid
       │OK
       ▼
  Temukan orphan children (child tanpa parent)
  ──Ada?──► Log WARNING (tidak error, hanya peringatan)
       │
Return True (valid)
```

---

## `embedder.py` — Pipeline Embedding & Upload ke Database

Mengubah teks dokumen menjadi vektor embedding dan menyimpannya ke Supabase.

```
run_ingestion(child_chunks_path, parent_chunks_path)
       │
       ▼
STEP 1: Load & Validasi
  load_child_chunks()  → list child dicts
  load_parent_chunks() → list parent dicts
  validate_parent_child_links()
       │
       ▼
STEP 2: Build Mapping
  build_child_to_parent_map(parents)
  → {child_id: parent_id, ...}
       │
       ▼
STEP 3: Generate Embeddings
  get_openai_embeddings(child_texts)
    ├─ Split menjadi batch @20 teks
    ├─ Setiap batch: OpenAI embeddings.create(dim=2000)
    ├─ Sleep 0.5 detik antar batch (hindari rate limit)
    └─ Return list vektor [float x 2000]
       │
       ▼
STEP 4: Upload Parent Chunks
  upsert_parent_chunks(parents)
    ├─ Cek parent_id yang sudah ada di DB
    ├─ Filter hanya yang baru
    └─ Supabase INSERT ke "parent_documents"
       │
       ▼
STEP 5: Upload Child Chunks + Embedding
  upsert_child_chunks_with_embeddings(children, embeddings, mapping)
    ├─ Cek child_id yang sudah ada di DB
    ├─ Filter hanya yang baru
    ├─ Batch @20: INSERT ke "child_documents" + embedding vektor
    └─ pgvector menyimpan embedding untuk pencarian similarity
       │
       ▼
Return stats:
  {total_parents, total_children,
   new_parents_inserted, new_children_inserted,
   embedding_dimension}
```

> **Kapan dijalankan?** Hanya sekali (atau saat ada data baru) via `python main.py --ingest`.
