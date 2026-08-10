-- =======================================================================================
-- FILE: supabase_migration_admin_status.sql
-- TUJUAN: Migrasi database untuk mendukung fitur Admin Dashboard (Increment 3)
--         dengan penambahan status persisten pada chunk dokumen.
-- =======================================================================================

-- 1. PENAMBAHAN STATUS EMBEDDING & UPDATED_AT PADA CHILD_DOCUMENTS
-- Status default 'success' karena data eksisting (Increment 1 & 2) 
-- sudah ter-embed seluruhnya melalui script loader & embedder di awal.
ALTER TABLE child_documents
  ADD COLUMN embedding_status TEXT NOT NULL DEFAULT 'success'
    CHECK (embedding_status IN ('pending', 'stale', 'success', 'failed')),
  ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- 2. PENAMBAHAN UPDATED_AT PADA PARENT_DOCUMENTS
ALTER TABLE parent_documents
  ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
