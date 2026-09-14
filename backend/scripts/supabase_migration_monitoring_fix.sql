-- Migration: Tambah kolom stage_self_query_ms dan cache_hit ke tabel request_metrics
-- Tanggal: 2026-09-02
-- Konteks: Bug fix monitoring — dua kolom ini hilang dari skema awal:
--   1. stage_self_query_ms: pipeline.py sudah memanggil start_stage("self_query")
--      tapi kolom DB-nya tidak pernah dibuat, jadi data timing hilang senyap setiap request.
--   2. cache_hit: ai_services.py memanggil set_field(cache_hit=...) tapi field ini
--      belum ada di RequestMetricsCollector maupun di skema DB.
-- Setelah menjalankan migration ini, PERLU reload schema cache Supabase (PostgREST restart
-- atau tunggu auto-refresh) agar kolom baru muncul di API.

-- Jalankan di Supabase SQL Editor.

ALTER TABLE request_metrics
    ADD COLUMN IF NOT EXISTS stage_self_query_ms DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS cache_hit BOOLEAN;

-- Komentar untuk dokumentasi kolom baru
COMMENT ON COLUMN request_metrics.stage_self_query_ms IS
    'Durasi tahap self-query parsing (extract_query_components) dalam milidetik. '
    'NULL jika tahap ini dilewati atau tidak terinstrumentasi di request tersebut.';

COMMENT ON COLUMN request_metrics.cache_hit IS
    'True jika hasil retrieval diambil dari TTL cache di ai_services.py (bukan pipeline penuh). '
    'False jika cache miss — pipeline retrieval dijalankan sepenuhnya. '
    'NULL untuk request lama sebelum kolom ini ditambahkan.';
