# Pseudocode untuk `scripts/supabase_migration_multidomain.sql`

```markdown
ALGORITMA SKEMA DATABASE MULTI-DOMAIN DAN AUTENTIKASI (supabase_migration_multidomain.sql)

1. MODIFIKASI TABEL DOKUMEN (PARENT & CHILD)
   - TAMBAHKAN kolom `domain` (Teks) pada tabel `parent_documents` dan `child_documents`.
   - SETEL nilai default kolom `domain` menjadi 'PI'.
   - BERIKAN batasan (CHECK CONSTRAINT) agar nilai `domain` hanya boleh salah satu dari: 'PI', 'KKP', 'SKRIPSI', 'NON_SKRIPSI'.
   - BUAT INDEX B-Tree pada kolom `domain` di tabel `child_documents` untuk mempercepat proses pencarian (filtering).

2. PEMBUATAN TABEL AKUN MAHASISWA (mahasiswa_accounts)
   - BUAT TABEL `mahasiswa_accounts` dengan kolom:
     - `mahasiswa_id` (UUID, Primary Key, Auto Generate).
     - `google_sub` (Teks, Unik, Tidak Boleh Kosong): Menyimpan ID dari Google OAuth.
     - `email`, `nama`, `avatar_url` (Teks): Data profil pengguna.
     - `created_at`, `last_login` (Timestamp): Penanda waktu aktivitas.

3. MODIFIKASI TABEL SESI PERCAKAPAN (conversation_sessions)
   - TAMBAHKAN kolom `channel` (Teks) pada tabel `conversation_sessions`.
   - SETEL nilai default `channel` menjadi 'telegram'.
   - BERIKAN batasan (CHECK CONSTRAINT) agar nilai `channel` hanya boleh: 'telegram' atau 'website'.
   - TAMBAHKAN kolom `mahasiswa_id` (UUID) sebagai Foreign Key yang merujuk ke tabel `mahasiswa_accounts`.
   - SETEL agar jika data akun mahasiswa dihapus, nilai ini diset menjadi NULL (ON DELETE SET NULL).

4. PEMBUATAN TABEL AKUN ADMIN (admin_users)
   - BUAT TABEL `admin_users` dengan kolom:
     - `admin_id` (UUID, Primary Key, Auto Generate).
     - `username` (Teks, Unik, Tidak Boleh Kosong).
     - `password_hash` (Teks, Tidak Boleh Kosong): Hash kata sandi untuk keamanan.
     - `full_name` (Teks): Nama lengkap admin.
     - `created_at`, `last_login` (Timestamp).

5. PEMBUATAN TABEL LOG AUDIT EDIT CHUNK (chunk_edit_logs)
   - BUAT TABEL `chunk_edit_logs` dengan kolom:
     - `log_id` (UUID, Primary Key, Auto Generate).
     - `child_id` (Teks, Foreign Key ke `child_documents`, ON DELETE CASCADE).
     - `parent_id` (Teks, Foreign Key ke `parent_documents`, ON DELETE CASCADE).
     - `admin_id` (UUID, Foreign Key ke `admin_users`, ON DELETE SET NULL).
     - `old_content`, `new_content` (Teks): Riwayat teks sebelum dan sesudah perubahan.
     - `status` (Teks, Default 'pending'): Status pemrosesan ulang embedding.
     - BERIKAN batasan (CHECK CONSTRAINT) pada `status` ('pending', 'processing', 'success', 'failed').
     - `error_message` (Teks): Catatan jika proses re-embedding gagal.
     - `edited_at`, `reembedded_at` (Timestamp).
   - BUAT INDEX pada kolom `status` di tabel `chunk_edit_logs` untuk mempercepat filter antrean re-embedding di Dashboard Admin.
```
