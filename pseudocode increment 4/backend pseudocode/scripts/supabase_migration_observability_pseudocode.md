# Pseudocode untuk `scripts/supabase_migration_observability.sql`

```markdown
ALGORITMA MIGRASI DATABASE OBSERVABILITY (supabase_migration_observability.sql)

Menambahkan tabel request_metrics untuk mencatat timing, token, cost, error,
dan kualitas retrieval per request chat. Tidak mengubah tabel yang sudah ada.

1. CREATE TABLE request_metrics (jika belum ada)
   
   FIELD IDENTITAS:
   - id (BIGINT, PK, auto-increment)
   - request_id (UUID, NOT NULL, DEFAULT gen_random_uuid())
   - created_at (TIMESTAMPTZ, NOT NULL, DEFAULT now())
   - session_id (TEXT, nullable)
   - mahasiswa_id (TEXT, nullable)
   - channel (TEXT, NOT NULL, DEFAULT 'unknown') — 'website' | 'telegram'
   
   FIELD STATUS AKHIR:
   - status (TEXT, NOT NULL, DEFAULT 'success') — 'success' | 'error' | 'quota_rejected'
   - error_type (TEXT, nullable) — nama class exception Python
   - error_source (TEXT, nullable) — 'openai' | 'supabase' | 'validation' | 'rate_limit' | 'unknown'
   - http_status (INT, nullable)
   
   FIELD TIMING PIPELINE (semua NUMERIC, nullable):
   - stage_validation_ms
   - stage_session_load_ms
   - stage_reformulation_ms — nullable, 0 jika tidak triggered
   - stage_embedding_ms
   - stage_retrieval_ms
   - stage_reranking_ms
   - stage_parent_assembly_ms
   - stage_generation_ms
   - stage_db_save_ms
   - total_ms
   
   FIELD KUALITAS RETRIEVAL:
   - num_docs_retrieved (INT, nullable) — hasil hybrid search sebelum rerank
   - num_docs_after_rerank (INT, nullable) — hasil setelah threshold
   - top_cross_encoder_score (NUMERIC, nullable)
   - avg_cross_encoder_score (NUMERIC, nullable)
   - domain_detected (TEXT, nullable) — 'PI'|'KKP'|'SKRIPSI'|'NON_SKRIPSI'|'UNKNOWN'
   - is_no_relevant_doc (BOOLEAN, NOT NULL, DEFAULT FALSE)
   - retrieved_parent_ids (TEXT[], nullable) — array parent_id yang masuk context LLM
   - rewrite_method (TEXT, nullable) — 'None'|'Rule'|'LLM'
   
   FIELD TOKEN & COST:
   - input_tokens (INT, nullable)
   - output_tokens (INT, nullable)
   - embedding_tokens (INT, nullable) — estimasi
   - llm_cost_usd (NUMERIC(12,6), nullable)
   - embedding_cost_usd (NUMERIC(12,6), nullable)
   
   FIELD RELIABILITY:
   - openai_retry_count (INT, NOT NULL, DEFAULT 0)
   
   FIELD INVESTIGASI/DRILL-DOWN (G1-G6):
   - question (TEXT, nullable) — teks pertanyaan asli
   - username (TEXT, nullable) — nama tampilan user
   - retrieval_detail (JSONB, nullable) — semua kandidat dokumen beserta skor
     Format: [{"parent_id":"...", "title":"...", "score":0.82, "accepted":true}, ...]

2. CREATE INDEX (jika belum ada):
   - idx_request_metrics_created_at — untuk query agregasi time-based
   - idx_request_metrics_session_id — untuk lookup per sesi
   - idx_request_metrics_channel — untuk filter per channel
   - idx_request_metrics_status — untuk filter success/error/quota_rejected
   - idx_request_metrics_domain — untuk filter per domain
   - idx_request_metrics_mahasiswa_id — untuk query per user
   - idx_request_metrics_domain_no_doc (domain_detected, is_no_relevant_doc)
     — untuk query "list pertanyaan no-relevant-doc per domain" (G4/G6)

3. ROW LEVEL SECURITY:
   - Enable RLS pada tabel request_metrics.
   - Buat policy: hanya service_role yang boleh SELECT, INSERT, UPDATE, DELETE.
   - Ikuti pola RLS yang sama seperti tabel lain di project ini.

CATATAN:
   - Tabel chat_logs yang sudah ada TIDAK diubah/dihapus.
   - Jika tabel request_metrics sudah ada tanpa kolom question/username/retrieval_detail,
     jalankan ALTER TABLE ADD COLUMN IF NOT EXISTS untuk ketiga kolom tersebut.
```
