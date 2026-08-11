# Pseudocode: Admin API Endpoints

## File: `src/api/admin.py`

```markdown
ALGORITMA ADMIN API ENDPOINTS (admin.py)

1. IMPOR PUSTAKA & SETUP
   - FastAPI (APIRouter, HTTPException, Depends, BackgroundTasks)
   - Pydantic models untuk request/response validation
   - Admin auth functions (get_current_admin, authenticate_admin, issue_admin_token)
   - Chunk editor functions
   - Supabase Client
   - Settings konfigurasi

2. ROUTER INITIALIZATION
   - APIRouter dengan prefix="/admin" dan tags=["Admin"]

3. PYDANTIC MODELS
   - AdminLoginRequest: {username, password}
   - AdminLoginResponse: {access_token, admin}
   - ChunkSaveRequest: {title?, pages?, content?}  
   - ChunkSaveResponse: {child_id, embedding_status, content_changed, message}
   - ReembedTriggerResponse: {log_id, child_id, status, message}
   - ChunkDetailResponse: {id, title, pages, content, embedding_status, reembedded_at, parent, section, domain, source}
   - DeleteResponse: {deleted: True, parent_deleted, message}
   - ChunkEditStatusResponse: {status, error_message?, edited_at, reembedded_at?}

4. DEPENDENCY FUNCTIONS
   - get_supabase(): Factory function untuk Supabase client

5. ENDPOINT POST "/login"
   - Path: /admin/login
   - Input: AdminLoginRequest (username, password)
   - ALGORITMA:
     - TAHAP 1: Authenticate admin
       - Panggil authenticate_admin(username, password, supabase)
       - JIKA gagal: HTTPException 401 "Invalid username or password"
     - TAHAP 2: Issue JWT token
       - Panggil issue_admin_token(admin)
     - TAHAP 3: Return response
       - AdminLoginResponse dengan access_token dan admin info

6. ENDPOINT POST "/logout" 
   - Path: /admin/logout
   - Dependency: get_current_admin (untuk validasi token)
   - KEMBALIKAN {"message": "Logged out successfully"}
   - Note: JWT stateless, client harus hapus token

7. ENDPOINT GET "/documents"
   - Path: /admin/documents  
   - Dependency: get_current_admin
   - ALGORITMA:
     - Panggil chunk_editor.list_knowledge_tree(supabase)
     - KEMBALIKAN full knowledge tree structure untuk dashboard

8. ENDPOINT GET "/chunks/{child_id}"
   - Path: /admin/chunks/{child_id}
   - Dependency: get_current_admin
   - ALGORITMA:
     - COBA panggil chunk_editor.get_chunk_detail(child_id, supabase)
     - JIKA ResourceNotFoundError: HTTPException 404
     - KEMBALIKAN ChunkDetailResponse

9. ENDPOINT PUT "/chunks/{child_id}"
   - Path: /admin/chunks/{child_id}
   - Input: ChunkSaveRequest (title?, pages?, content?)
   - Dependency: get_current_admin
   - ALGORITMA:
     - Validate minimal satu field harus ada untuk update
     - JIKA semua field None: HTTPException 400
     - COBA panggil chunk_editor.save_chunk(child_id, admin["sub"], supabase, title, pages, content)
     - JIKA ResourceNotFoundError: HTTPException 404
     - KEMBALIKAN ChunkSaveResponse

10. ENDPOINT POST "/chunks/{child_id}/reembed"
    - Path: /admin/chunks/{child_id}/reembed
    - Dependency: get_current_admin, BackgroundTasks
    - ALGORITMA:
      - TAHAP 1: Trigger reembed preparation
        - COBA panggil chunk_editor.trigger_reembed(child_id, admin["sub"], supabase)
        - JIKA ResourceNotFoundError: HTTPException 404
      - TAHAP 2: Schedule background task
        - background_tasks.add_task(chunk_editor.process_chunk_reembed, ...)
        - Pass semua parameter yang diperlukan (log_id, child_id, parent_id, old_content, new_content, supabase, settings)
      - TAHAP 3: Return immediate response
        - ReembedTriggerResponse dengan status "processing"
        - Message: "Proses re-embed berjalan. Cek progres via GET /chunks/{child_id}/edit-status."

11. ENDPOINT DELETE "/chunks/{child_id}"
    - Path: /admin/chunks/{child_id}
    - Dependency: get_current_admin
    - ALGORITMA:
      - COBA panggil chunk_editor.delete_chunk(child_id, supabase)  
      - JIKA ResourceNotFoundError: HTTPException 404
      - Prepare delete message dengan parent cleanup info
      - KEMBALIKAN DeleteResponse

12. ENDPOINT GET "/chunks/{child_id}/edit-status"
    - Path: /admin/chunks/{child_id}/edit-status
    - Dependency: get_current_admin
    - ALGORITMA:
      - Panggil chunk_editor.get_edit_status(child_id, supabase)
      - JIKA tidak ada history: HTTPException 404 "No edit history found"
      - KEMBALIKAN ChunkEditStatusResponse
```

**Security & Design Patterns:**
- Semua endpoint protected dengan get_current_admin dependency
- Consistent error handling dengan HTTPException
- Background tasks untuk long-running operations (re-embedding)
- Proper REST API design dengan appropriate HTTP methods
- Comprehensive response models dengan type safety
- Resource ownership validation melalui admin authentication