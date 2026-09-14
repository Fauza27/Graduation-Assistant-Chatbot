# Fix untuk Bug Constraint embedding_status

## Ringkasan Masalah

Ditemukan bug kritis dalam constraint database yang menyebabkan **seluruh fitur re-embedding tidak pernah bisa bekerja** sejak awal implementasi.

### Root Cause

**Constraint Database:**
```sql
-- Yang ada saat ini (SALAH)
CHECK (embedding_status IN ('pending', 'stale', 'success', 'failed'))
```

**Kode Python yang mencoba dijalankan:**
```python
# Di chunk_editor.py baris 668
update_result = supabase.table("child_documents").update({
    "embedding_status": "processing"  # ❌ TIDAK ADA dalam constraint!
}).eq("id", child_id).execute()
```

### Dampak

- Setiap kali admin mencoba trigger re-embedding chunk, database menolak dengan constraint violation
- Error ini tidak ter-handle dengan baik, menyebabkan 500 error untuk admin
- Fitur re-embedding yang sudah dikembangkan dengan compare-and-swap pattern tidak pernah benar-benar teruji

## Solusi

### 1. SQL Migration

File: `backend/scripts/supabase_migration_fix_embedding_status.sql`

```sql
-- Drop constraint lama
ALTER TABLE child_documents 
DROP CONSTRAINT IF EXISTS child_documents_embedding_status_check;

-- Tambah constraint baru yang mengizinkan 'processing'
ALTER TABLE child_documents 
ADD CONSTRAINT child_documents_embedding_status_check 
CHECK (embedding_status IN ('pending', 'stale', 'processing', 'success', 'failed'));
```

### 2. Verifikasi

Setelah migrasi dijalankan, constraint yang benar harus terlihat:

```sql
-- Query untuk memverifikasi
SELECT conname, consrc 
FROM pg_constraint 
WHERE conrelid = 'child_documents'::regclass 
  AND conname = 'child_documents_embedding_status_check';
```

## Flow yang Sekarang Akan Bekerja

1. **Admin edit chunk content** → `embedding_status = 'stale'` ✅
2. **Admin trigger re-embed** → `embedding_status = 'processing'` ✅ (setelah fix)
3. **Background process selesai** → `embedding_status = 'success'` ✅

## Status Terkait

### ✅ Yang Sudah Benar

- **`chunk_edit_logs.status`** sudah mengizinkan `'processing'` dari awal:
  ```sql
  CHECK (status IN ('pending', 'processing', 'success', 'failed'))
  ```

- **Section filtering di `hybrid_search`** sudah menggunakan `ILIKE '%' || filter_section || '%'` yang benar untuk struktur hierarkis

### 🔴 Yang Masih Perlu Diperbaiki

- Hanya constraint `child_documents.embedding_status` yang perlu ditambahi `'processing'`

## Test Cases Setelah Fix

1. **Edit chunk content:**
   ```python
   # Harus berhasil tanpa error
   PUT /admin/chunks/{child_id}/edit
   # embedding_status otomatis jadi 'stale'
   ```

2. **Trigger re-embedding:**
   ```python
   # Harus berhasil, tidak lagi constraint violation  
   POST /admin/chunks/{child_id}/reembed
   # embedding_status jadi 'processing'
   ```

3. **Monitor progress:**
   ```python
   # Harus bisa track sampai 'success'
   GET /admin/chunks/{child_id}/edit-status
   ```

## Catatan Teknis

- Migration ini adalah **zero-downtime** - hanya mengubah metadata constraint, tidak mengubah data yang ada
- Semua nilai `embedding_status` yang sudah ada (`'success'`, `'stale'`, dll) tetap valid
- Tidak perlu data migration atau reindex