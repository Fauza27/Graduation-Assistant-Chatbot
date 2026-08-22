# Pseudocode: Chunk Editor System

## File: `src/admin/chunk_editor.py`

```markdown
ALGORITMA CHUNK EDITOR & RE-EMBEDDING SYSTEM (chunk_editor.py)

1. IMPOR PUSTAKA
   - datetime, loguru logger
   - Supabase Client
   - ResourceNotFoundError dari auth
   - get_openai_embeddings dari ingestion.embedder

2. FUNGSI list_knowledge_tree(supabase: Client) -> dict
   - Tujuan: Mengambil struktur knowledge base lengkap untuk admin dashboard
   - TAHAP 1: Fetch semua parent documents
     - Query: SELECT parent_id, title, domain, section, updated_at FROM parent_documents ORDER BY domain, section, parent_id
   - TAHAP 2: Fetch semua child documents (lightweight)
     - Query: SELECT id, parent_id, title, pages, source, embedding_status, updated_at FROM child_documents ORDER BY parent_id, pages
   - TAHAP 3: Build parent_id -> source mapping
     - Loop child documents, ambil source dari first child sebagai representative parent source
   - TAHAP 4: Group children by parent_id
     - Buat dictionary children_by_parent untuk akses cepat
   - TAHAP 5: Build hierarchical tree structure
     - Group by (domain, source) -> chapters -> parents -> children
     - Format struktur tree untuk frontend consumption
   - TAHAP 6: Calculate summary statistics
     - total_documents, total_parents, total_children, last_updated_at
   - KEMBALIKAN {"summary": summary, "documents": documents_list}

3. FUNGSI get_chunk_detail(child_id: str, supabase: Client) -> dict
   - Query child document dengan all fields
   - JIKA tidak ditemukan: LEMPAR ResourceNotFoundError
   - Query parent info untuk context (title, section)
   - Query reembedded_at dari chunk_edit_logs (latest success)
   - Format pages dari TEXT[] ke comma-separated string untuk frontend
   - KEMBALIKAN detail lengkap chunk untuk editing form

4. FUNGSI save_chunk(child_id: str, admin_id: str, supabase: Client, title=None, pages=None, content=None) -> dict
   - TAHAP 1: Validate chunk exists
     - Query existing chunk data
     - JIKA tidak ditemukan: LEMPAR ResourceNotFoundError
   - TAHAP 2: Prepare updates
     - Compare new values dengan existing values
     - Set content_changed = True jika content berubah
     - Convert pages dari string ke TEXT[] untuk database
   - TAHAP 3: Update database
     - UPDATE child_documents SET ... WHERE id = child_id
     - Set embedding_status = 'stale' jika content berubah
     - Set updated_at = now()
   - TAHAP 4: Create audit log (jika content berubah)
     - INSERT INTO chunk_edit_logs (child_id, parent_id, admin_id, old_content, new_content, status = 'pending')
   - KEMBALIKAN status update dan message

5. FUNGSI trigger_reembed(child_id: str, admin_id: str, supabase: Client) -> dict
   - TAHAP 1: Validate chunk exists
     - Query parent_id dan content dari child_documents
   - TAHAP 2: Find atau create pending log entry
     - Cari pending log entry untuk chunk ini
     - JIKA ada: gunakan data tersebut
     - JIKA tidak ada: buat log entry baru untuk first-embed atau retry
   - TAHAP 3: Mark log sebagai processing
     - UPDATE chunk_edit_logs SET status = 'processing'
   - KEMBALIKAN data untuk background task (log_id, parent_id, old_content, new_content)

6. FUNGSI ASYNC process_chunk_reembed(log_id, child_id, parent_id, old_content, new_content, supabase, settings)
   - **BACKGROUND TASK** untuk actual re-embedding process
   - TAHAP 1: Generate new embedding
     - COBA call get_openai_embeddings([new_content])
     - Ambil vector result pertama
   - TAHAP 2: Update child document
     - UPDATE child_documents SET embedding = vector, embedding_status = 'success', updated_at = now()
   - TAHAP 3: Sync parent content (jika edit, bukan first-embed)
     - JIKA old_content tidak None:
       - Query parent content
       - Replace old_content dengan new_content di parent
       - UPDATE parent_documents SET content = new_parent_content, updated_at = now()
   - TAHAP 4: Mark log as success
     - UPDATE chunk_edit_logs SET status = 'success', reembedded_at = now()
   - TAHAP 5: Error handling
     - JIKA ada exception: mark embedding_status = 'failed', log status = 'failed', catat error_message

7. FUNGSI get_edit_status(child_id: str, supabase: Client) -> dict | None
   - Query latest chunk_edit_logs untuk child_id ini
   - Order by edited_at DESC, ambil yang terbaru
   - KEMBALIKAN status info (log_id, child_id, status, error_message, edited_at, reembedded_at)
   - JIKA tidak ada history: KEMBALIKAN None

8. FUNGSI delete_chunk(child_id: str, supabase: Client) -> dict
   - TAHAP 1: Validate chunk exists dan ambil parent_id
   - TAHAP 2: Delete chunk dari database
     - DELETE FROM child_documents WHERE id = child_id
     - Postgres CASCADE akan otomatis delete chunk_edit_logs
   - TAHAP 3: Update parent child_ids array
     - Fetch parent child_ids array
     - Remove child_id dari array
     - UPDATE parent_documents SET child_ids = new_array, updated_at = now()
   - TAHAP 4: Housekeeping - cek apakah parent menjadi orphan
     - Count sisa children untuk parent ini
     - JIKA count = 0: DELETE parent_documents (orphaned parent cleanup)
   - KEMBALIKAN info deletion (child_id, parent_id, parent_deleted boolean)
```

**Key Features:**
- Real-time chunk editing dengan audit trail
- Background re-embedding tasks untuk performa
- Parent-child content synchronization
- Automatic orphaned parent cleanup
- Comprehensive error handling dan status tracking