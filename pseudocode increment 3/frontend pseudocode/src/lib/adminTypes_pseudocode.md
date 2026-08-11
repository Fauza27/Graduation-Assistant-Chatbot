# Pseudocode: Admin TypeScript Types

## File: `lib/adminTypes.ts`

```markdown
ALGORITMA ADMIN TYPESCRIPT TYPES (adminTypes.ts)

1. ENUM TYPES
   - EmbeddingStatus = 'pending' | 'stale' | 'success' | 'failed'
   - EditLogStatus = 'pending' | 'processing' | 'success' | 'failed'

2. INTERFACE ChildLite
   - Tujuan: Lightweight child data untuk tree view
   - Properties:
     - id: string
     - title: string
     - pages: string (comma-separated untuk display)
     - embedding_status: EmbeddingStatus

3. INTERFACE ParentNode  
   - Tujuan: Parent document dalam knowledge tree
   - Properties:
     - parent_id: string
     - title: string
     - child_count: number
     - children: ChildLite[]

4. INTERFACE ChapterNode
   - Tujuan: Chapter/section grouping dalam tree
   - Properties:
     - section: string (e.g., "BAB I", "BAB II")
     - parents: ParentNode[]

5. INTERFACE DocumentNode
   - Tujuan: Top-level document grouping
   - Properties:
     - domain: string ('PI' | 'KKP' | 'SKRIPSI' | 'NON_SKRIPSI')
     - source: string (document filename)
     - chapters: ChapterNode[]

6. INTERFACE SummaryStats
   - Tujuan: Dashboard statistics
   - Properties:
     - total_documents: number
     - total_parents: number  
     - total_children: number
     - last_updated_at: string (ISO timestamp)

7. INTERFACE KnowledgeTreeResponse
   - Tujuan: Complete tree structure dari GET /admin/documents
   - Properties:
     - summary: SummaryStats
     - documents: DocumentNode[]

8. INTERFACE ChunkDetail
   - Tujuan: Full chunk data untuk editing
   - Properties:
     - id: string
     - title: string
     - pages: string
     - content: string (full text content)
     - embedding_status: EmbeddingStatus
     - reembedded_at: string | null (last successful re-embed)
     - parent: {parent_id: string; title: string}
     - section: string
     - domain: string
     - source: string

9. INTERFACE ChunkEditStatus
   - Tujuan: Status tracking untuk re-embed operations
   - Properties:
     - log_id: string
     - child_id: string
     - status: EditLogStatus
     - error_message: string | null
     - edited_at: string (ISO timestamp)
     - reembedded_at: string | null
```

**Type System Features:**
- Comprehensive type coverage untuk semua API responses
- Hierarchical tree structure types (Document -> Chapter -> Parent -> Child)
- Status enums untuk type safety pada embedding states
- Nullable types untuk optional fields
- ISO timestamp strings untuk consistent date handling
- Lightweight vs detailed interfaces untuk performance optimization