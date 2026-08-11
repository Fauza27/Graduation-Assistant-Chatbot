# Pseudocode: Admin API Client

## File: `lib/adminApi.ts`

```markdown
ALGORITMA ADMIN API CLIENT (adminApi.ts)

1. IMPOR DEPENDENCIES
   - getAdminToken, adminLogout dari adminAuth
   - Types dari adminTypes: KnowledgeTreeResponse, ChunkDetail, ChunkEditStatus

2. FUNGSI adminFetch(path: string, options: RequestInit = {})
   - Tujuan: Wrapper untuk fetch dengan admin authentication dan error handling
   - TAHAP 1: Get dan validate token
     - const token = getAdminToken()
     - JIKA tidak ada token: adminLogout() dan throw Error('Unauthorized')
   - TAHAP 2: Prepare headers
     - Create Headers object dari options.headers
     - Set Authorization: `Bearer ${token}`
     - Set Content-Type: 'application/json' (jika belum ada)
   - TAHAP 3: Build URL dan send request
     - url = `${NEXT_PUBLIC_API_BASE_URL}/api/admin${path}`
     - await fetch(url, {...options, headers})
   - TAHAP 4: Handle response status
     - JIKA 401: adminLogout() dan throw Error('Sesi kedaluwarsa. Silakan login kembali.')
     - JIKA 403: throw Error('Akun ini bukan admin.')
     - JIKA not ok: Extract error message dari response.json() atau use generic message
   - TAHAP 5: Return JSON
     - return response.json()

3. FUNGSI getKnowledgeTree(): Promise<KnowledgeTreeResponse>
   - return adminFetch('/documents', {method: 'GET'})

4. FUNGSI getChunkDetail(childId: string): Promise<ChunkDetail>
   - return adminFetch(`/chunks/${childId}`, {method: 'GET'})

5. INTERFACE ChunkSaveResponse
   - message: string
   - embedding_status: 'pending' | 'stale' | 'success' | 'failed'
   - content_changed: boolean

6. FUNGSI saveChunk(childId: string, updates: {title?, pages?, content?}): Promise<ChunkSaveResponse>
   - return adminFetch(`/chunks/${childId}`, {
       method: 'PUT',
       body: JSON.stringify(updates)
     })

7. INTERFACE ReembedTriggerResponse
   - message: string
   - log_id: string
   - status: 'pending' | 'processing' | 'success' | 'failed'

8. FUNGSI triggerReembed(childId: string): Promise<ReembedTriggerResponse>
   - return adminFetch(`/chunks/${childId}/reembed`, {method: 'POST'})

9. FUNGSI getEditStatus(childId: string): Promise<ChunkEditStatus>
   - return adminFetch(`/chunks/${childId}/edit-status`, {method: 'GET'})

10. INTERFACE DeleteResponse
    - message: string
    - parent_deleted: boolean

11. FUNGSI deleteChunk(childId: string): Promise<DeleteResponse>
    - return adminFetch(`/chunks/${childId}`, {method: 'DELETE'})
```

**API Client Features:**
- Centralized authentication dengan auto-logout pada 401
- Consistent error handling dan user-friendly messages
- Type-safe interfaces untuk semua responses
- REST API pattern dengan proper HTTP methods
- Automatic JSON parsing dan Content-Type headers