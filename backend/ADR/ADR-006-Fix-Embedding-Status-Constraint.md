# ADR-006: Fix Embedding Status Constraint

**Status:** Accepted  
**Date:** 2026-09-10  
**Deciders:** Database Schema Review  

## Context

Ditemukan bug kritis dalam constraint database yang mencegah fitur re-embedding chunk bekerja sama sekali sejak implementasi awal. Root cause adalah constraint `child_documents.embedding_status` yang tidak mengizinkan nilai `'processing'` yang dibutuhkan oleh kode aplikasi.

### Problem Statement

```sql
-- Constraint yang ada (BROKEN)
CHECK (embedding_status IN ('pending', 'stale', 'success', 'failed'))

-- Kode aplikasi mencoba (di chunk_editor.py)
"embedding_status": "processing"  -- ❌ Tidak diizinkan constraint!
```

Setiap kali admin mencoba trigger re-embedding, database menolak operasi dengan constraint violation, menyebabkan:
- 500 error pada admin interface
- Fitur re-embedding tidak pernah bisa digunakan
- Compare-and-swap pattern yang sudah dikembangkan tidak pernah teruji

## Decision

Kami memutuskan untuk memperbaiki constraint database dengan menambahkan `'processing'` ke daftar nilai yang diizinkan.

### Technical Solution

```sql
-- Drop constraint lama
ALTER TABLE child_documents 
DROP CONSTRAINT IF EXISTS child_documents_embedding_status_check;

-- Tambah constraint baru dengan 'processing'
ALTER TABLE child_documents 
ADD CONSTRAINT child_documents_embedding_status_check 
CHECK (embedding_status IN ('pending', 'stale', 'processing', 'success', 'failed'));
```

## Consequences

### Positive

- ✅ Fitur re-embedding akan berfungsi untuk pertama kalinya
- ✅ Admin dapat trigger re-embedding chunk yang sudah diedit
- ✅ Compare-and-swap pattern di chunk_editor.py akan bekerja sesuai desain
- ✅ Zero downtime migration (hanya metadata change)

### Neutral

- 🔄 Perlu testing menyeluruh untuk memverifikasi flow re-embedding end-to-end
- 🔄 Dokumentasi perlu diupdate untuk mencerminkan constraint yang benar

### Risk Mitigation

- **Low Risk Migration:** Hanya mengubah constraint metadata, tidak mengubah data existing
- **Backward Compatible:** Semua nilai `embedding_status` yang sudah ada tetap valid
- **Rollback Plan:** Dapat di-rollback dengan mengembalikan constraint lama (jika tidak ada data 'processing' tersisa)

## Implementation

### Files Created/Modified

1. **Migration Script:** `scripts/supabase_migration_fix_embedding_status.sql`
2. **Documentation:** `docs/EMBEDDING_STATUS_CONSTRAINT_FIX.md`
3. **PowerShell Script:** `scripts/run_embedding_fix.ps1`
4. **ADR Record:** `ADR/ADR-006-Fix-Embedding-Status-Constraint.md` (this file)

### Verification Steps

1. Apply migration ke database
2. Test chunk edit → verify `embedding_status = 'stale'`
3. Test re-embed trigger → verify `embedding_status = 'processing'`
4. Monitor background process → verify `embedding_status = 'success'`

## Related

- **ADR-001:** Arsitektur Sistem Utama (chunk management foundation)
- **Codebase:** `src/admin/chunk_editor.py` (re-embedding logic)
- **Database:** `child_documents` table schema