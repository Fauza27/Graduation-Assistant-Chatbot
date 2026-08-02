-- =======================================================================================
-- FILE: supabase_migration_multidomain.sql
-- TUJUAN: Migrasi database dari sistem PI (2 domain) menjadi sistem Skripsi (4 domain)
--         serta mendukung fitur autentikasi Website dan Admin Dashboard.
-- =======================================================================================

-- 1. PENAMBAHAN DOMAIN PADA DOKUMEN (PARENT & CHILD)
-- Default diisi 'PI' agar data eksisting tidak error (melanggar NOT NULL).
-- Nanti data KKP yang sudah ada bisa di-update manual (UPDATE ... WHERE source LIKE '%KKP%').
ALTER TABLE parent_documents 
ADD COLUMN domain TEXT NOT NULL DEFAULT 'PI'
CHECK (domain IN ('PI', 'KKP', 'SKRIPSI', 'NON_SKRIPSI'));

ALTER TABLE child_documents 
ADD COLUMN domain TEXT NOT NULL DEFAULT 'PI'
CHECK (domain IN ('PI', 'KKP', 'SKRIPSI', 'NON_SKRIPSI'));

-- Pembuatan Index B-Tree untuk mempercepat filter pencarian berdasarkan domain.
CREATE INDEX idx_child_documents_domain ON child_documents(domain);


-- 2. TABEL MAHASISWA ACCOUNTS (Untuk login Website via Google OAuth)
CREATE TABLE mahasiswa_accounts (
    mahasiswa_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_sub TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    nama TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_login TIMESTAMPTZ
);


-- 3. PERUBAHAN TABEL SESI PERCAKAPAN (Untuk mendukung multi-channel)
ALTER TABLE conversation_sessions 
ADD COLUMN channel TEXT NOT NULL DEFAULT 'telegram'
CHECK (channel IN ('telegram', 'website'));

-- Bisa bernilai NULL karena chat Telegram bersifat anonim (tidak login)
ALTER TABLE conversation_sessions 
ADD COLUMN mahasiswa_id UUID REFERENCES mahasiswa_accounts(mahasiswa_id) ON DELETE SET NULL;


-- 4. TABEL ADMIN USERS (Untuk Admin Dashboard)
CREATE TABLE admin_users (
    admin_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_login TIMESTAMPTZ
);


-- 5. TABEL CHUNK EDIT LOGS (Untuk Audit Trail & Antrian Re-Embedding)
CREATE TABLE chunk_edit_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    child_id TEXT NOT NULL REFERENCES child_documents(id) ON DELETE CASCADE,
    parent_id TEXT NOT NULL REFERENCES parent_documents(parent_id) ON DELETE CASCADE,
    admin_id UUID REFERENCES admin_users(admin_id) ON DELETE SET NULL,
    old_content TEXT,
    new_content TEXT,
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'processing', 'success', 'failed')),
    error_message TEXT,
    edited_at TIMESTAMPTZ DEFAULT now(),
    reembedded_at TIMESTAMPTZ
);

-- Index opsional tambahan untuk performa dashboard admin (memantau status log)
CREATE INDEX idx_chunk_edit_logs_status ON chunk_edit_logs(status);
