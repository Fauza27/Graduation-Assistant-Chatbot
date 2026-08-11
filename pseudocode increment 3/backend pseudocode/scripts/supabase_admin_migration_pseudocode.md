# Pseudocode: Database Schema Admin Status Migration

## File: `scripts/supabase_migration_admin_status.sql`

```markdown
ALGORITMA MIGRASI PENAMBAHAN STATUS ADMIN (supabase_migration_admin_status.sql)

1. PENAMBAHAN STATUS EMBEDDING & UPDATED_AT PADA CHILD_DOCUMENTS
   - TUJUAN: Mendukung pelacakan status chunk dokumen di Admin Dashboard.
   - TAHAP 1: Modifikasi tabel `child_documents`.
     - TAMBAHKAN kolom `embedding_status` (Teks, Tidak Boleh Kosong, Default 'success').
     - SETEL default 'success' karena data eksisting dianggap sudah berhasil di-embed.
     - BERIKAN batasan (CHECK CONSTRAINT) agar nilai `embedding_status` hanya boleh: 'pending', 'stale', 'success', 'failed'.
     - TAMBAHKAN kolom `updated_at` (Timestamp dengan zona waktu, Tidak Boleh Kosong, Default waktu saat ini/now()).

2. PENAMBAHAN UPDATED_AT PADA PARENT_DOCUMENTS
   - TUJUAN: Mendukung pelacakan kapan dokumen induk terakhir diperbarui.
   - TAHAP 1: Modifikasi tabel `parent_documents`.
     - TAMBAHKAN kolom `updated_at` (Timestamp dengan zona waktu, Tidak Boleh Kosong, Default waktu saat ini/now()).
```