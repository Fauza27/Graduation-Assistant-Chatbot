# Pseudocode: Database Schema Admin Migration

## File: `scripts/supabase_migration_multidomain.sql`

```markdown
ALGORITMA MIGRASI DATABASE UNTUK ADMIN SYSTEM (supabase_migration_multidomain.sql)

1. PENAMBAHAN KOLOM DOMAIN PADA DOKUMEN
   - Tujuan: Mendukung multi-domain (PI, KKP, SKRIPSI, NON_SKRIPSI) vs sistem lama yang hanya PI
   - TAHAP 1: Alter parent_documents table
     - ADD COLUMN domain TEXT NOT NULL DEFAULT 'PI'
     - ADD CHECK constraint (domain IN ('PI', 'KKP', 'SKRIPSI', 'NON_SKRIPSI'))
   - TAHAP 2: Alter child_documents table
     - ADD COLUMN domain TEXT NOT NULL DEFAULT 'PI'  
     - ADD CHECK constraint (domain IN ('PI', 'KKP', 'SKRIPSI', 'NON_SKRIPSI'))
   - TAHAP 3: Create performance indexes
     - CREATE INDEX idx_child_documents_domain ON child_documents(domain)
   
   Note: Default 'PI' untuk backward compatibility dengan data existing

2. TABEL MAHASISWA ACCOUNTS
   - Tujuan: Autentikasi mahasiswa untuk website (Google OAuth)
   - STRUKTUR TABEL:
     - mahasiswa_id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
     - google_sub: TEXT UNIQUE NOT NULL (Google OAuth subject ID)
     - email: TEXT NOT NULL
     - nama: TEXT (display name)
     - avatar_url: TEXT (profile picture URL)
     - created_at: TIMESTAMPTZ DEFAULT now()
     - last_login: TIMESTAMPTZ (tracking login activity)

3. PERUBAHAN TABEL CONVERSATION SESSIONS
   - Tujuan: Mendukung multi-channel (telegram + website) dan user tracking
   - TAHAP 1: Add channel column
     - ADD COLUMN channel TEXT NOT NULL DEFAULT 'telegram'
     - ADD CHECK constraint (channel IN ('telegram', 'website'))
   - TAHAP 2: Add mahasiswa reference
     - ADD COLUMN mahasiswa_id UUID REFERENCES mahasiswa_accounts(mahasiswa_id) ON DELETE SET NULL
     - Note: NULL untuk anonymous telegram users

4. TABEL ADMIN USERS  
   - Tujuan: Autentikasi admin untuk dashboard management
   - STRUKTUR TABEL:
     - admin_id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
     - username: TEXT UNIQUE NOT NULL
     - password_hash: TEXT NOT NULL (bcrypt hash)
     - full_name: TEXT (display name)
     - created_at: TIMESTAMPTZ DEFAULT now()
     - last_login: TIMESTAMPTZ (tracking login activity)

5. TABEL CHUNK EDIT LOGS
   - Tujuan: Audit trail dan antrian re-embedding untuk chunk yang diedit admin
   - STRUKTUR TABEL:
     - log_id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
     - child_id: TEXT NOT NULL REFERENCES child_documents(id) ON DELETE CASCADE
     - parent_id: TEXT NOT NULL REFERENCES parent_documents(parent_id) ON DELETE CASCADE
     - admin_id: UUID REFERENCES admin_users(admin_id) ON DELETE SET NULL
     - old_content: TEXT (content sebelum edit, NULL untuk first-embed)
     - new_content: TEXT (content setelah edit)
     - status: TEXT NOT NULL DEFAULT 'pending'
       - CHECK constraint (status IN ('pending', 'processing', 'success', 'failed'))
     - error_message: TEXT (jika status = 'failed')
     - edited_at: TIMESTAMPTZ DEFAULT now()
     - reembedded_at: TIMESTAMPTZ (timestamp ketika re-embed berhasil)
   - PERFORMANCE INDEXES:
     - CREATE INDEX idx_chunk_edit_logs_status ON chunk_edit_logs(status)
     - CREATE INDEX idx_chunk_edit_logs_child_id ON chunk_edit_logs(child_id)

6. ROW LEVEL SECURITY (RLS) SETUP
   - Enable RLS pada semua tabel baru:
     - mahasiswa_accounts
     - admin_users  
     - chunk_edit_logs
   - CREATE POLICY untuk service_role access:
     - Allow SELECT, INSERT, UPDATE, DELETE untuk service_role
     - Prevent direct user access, semua via backend API

7. MIGRATION TRACKING
   - INSERT migration marker ke user_quotas table
   - user_id = '_system_migration_multidomain'
   - Untuk tracking bahwa migration ini sudah dijalankan

8. DATA MIGRATION SCRIPT (Optional Manual Steps)
   - UPDATE existing data untuk set domain berdasarkan source patterns:
     - UPDATE parent_documents SET domain = 'KKP' WHERE source LIKE '%KKP%'
     - UPDATE child_documents SET domain = 'KKP' WHERE source LIKE '%KKP%'
     - Similar untuk SKRIPSI dan NON_SKRIPSI patterns
   - CREATE first admin user (manual via bcrypt hash):
     - INSERT INTO admin_users (username, password_hash, full_name) VALUES (...)
```

**Migration Safety Features:**
- Backward compatibility dengan default values
- CASCADE delete untuk referential integrity  
- Check constraints untuk data validation
- Performance indexes untuk query optimization
- RLS untuk security isolation
- Migration tracking untuk idempotency