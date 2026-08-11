# Pseudocode: Admin State Management

## File: `lib/adminStore.ts`

```markdown
ALGORITMA ADMIN STATE MANAGEMENT (adminStore.ts)

1. INTERFACE TYPES
   - Impor types dari adminTypes: KnowledgeTreeResponse, EmbeddingStatus
   - Impor function dari adminApi: getKnowledgeTree

2. INTERFACE AdminState
   - tree: KnowledgeTreeResponse | null (struktur knowledge base)
   - isTreeLoading: boolean (status loading tree)
   - selectedChildId: string | null (chunk yang sedang dipilih)
   - selectedParentKey: string | null (parent key untuk navigasi)
   
   ACTIONS:
   - fetchTree(): Promise<void> (fetch knowledge tree dari API)
   - selectChild(childId, parentKey): void (set selected chunk)
   - patchChunkInTree(childId, updates): void (update chunk data di tree)
   - removeChunkFromTree(childId, parentDeleted): void (hapus chunk dari tree)

3. ZUSTAND STORE IMPLEMENTATION
   - Gunakan create<AdminState> dari zustand
   - INITIAL STATE:
     - tree: null
     - isTreeLoading: false
     - selectedChildId: null
     - selectedParentKey: null

4. ACTION: fetchTree()
   - TAHAP 1: Set loading state
     - set({isTreeLoading: true})
   - TAHAP 2: Call API
     - COBA await getKnowledgeTree()
     - JIKA berhasil: set({tree: data, isTreeLoading: false})
     - JIKA error: 
       - console.error('Failed to fetch tree', error)
       - set({tree: null, isTreeLoading: false})

5. ACTION: selectChild(childId, parentKey)
   - Simple state update untuk navigation:
     - set({selectedChildId: childId, selectedParentKey: parentKey})

6. ACTION: patchChunkInTree(childId, updates)
   - Tujuan: Update chunk data di tree tanpa full re-fetch
   - TAHAP 1: Get current tree
     - const {tree} = get()
     - JIKA tree null: return early
   - TAHAP 2: Deep clone tree untuk immutability
     - const newTree = JSON.parse(JSON.stringify(tree))
   - TAHAP 3: Find dan update chunk
     - Nested loop melalui documents -> chapters -> parents -> children
     - Cari child dengan matching childId
     - Update child object dengan spread: {...child, ...updates}
     - Set found flag untuk early break
   - TAHAP 4: Update state jika found
     - JIKA found: set({tree: newTree})

7. ACTION: removeChunkFromTree(childId, parentDeleted)
   - Tujuan: Remove chunk dari tree dan handle parent cleanup
   - TAHAP 1: Get current tree dan deep clone
   - TAHAP 2: Find dan remove chunk
     - Nested loop melalui struktur tree
     - Splice child dari parent.children array
     - Decrement summary.total_children
   - TAHAP 3: Handle parent deletion
     - JIKA parentDeleted true:
       - Splice parent dari chapter.parents
       - Decrement summary.total_parents
       - JIKA chapter.parents kosong: remove entire chapter
   - TAHAP 4: Clear selection jika chunk yang dihapus sedang selected
     - JIKA selectedChildId === childId:
       - set({tree: newTree, selectedChildId: null, selectedParentKey: null})
     - SELAIN ITU: set({tree: newTree})
```

**State Management Features:**
- Zustand untuk lightweight state management
- Optimistic updates untuk performa (patch tanpa re-fetch)
- Immutable updates dengan deep cloning
- Automatic selection cleanup pada deletion
- Error handling untuk network failures
- Type-safe dengan TypeScript interfaces