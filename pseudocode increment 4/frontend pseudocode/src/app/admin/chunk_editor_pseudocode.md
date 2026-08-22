# Pseudocode: Chunk Editor Page

## File: `app/admin/dashboard/chunks/[childId]/page.tsx`

```markdown
ALGORITMA CHUNK EDITOR PAGE (chunks/[childId]/page.tsx)

1. COMPONENT SETUP
   - 'use client' directive
   - React hooks: useState, useEffect, use (untuk params)
   - useRouter, useAdminStore
   - Lucide icons (ChevronLeft, Info, Menu, Loader2)
   - Types: ChunkDetail dari adminTypes
   - Functions: getChunkDetail dari adminApi
   - Components: ChunkEditForm, KnowledgeTreeColumn

2. PARAMETER HANDLING
   - Destructure childId dari params Promise
   - Use React.use() untuk await params (Next.js 13+ pattern)

3. STATE MANAGEMENT
   - Local State:
     - detail: ChunkDetail | null (chunk data)
     - isLoading: boolean (loading state)
     - searchTree: string (tree search filter)
     - showInfoPanel: boolean (mobile info panel toggle)
   - Global State:
     - tree, fetchTree dari useAdminStore

4. DATA FETCHING EFFECTS
   - useEffect untuk tree initialization:
     - JIKA tree null: panggil fetchTree()
   - useEffect untuk chunk detail fetching:
     - Create isMounted flag untuk cleanup
     - setIsLoading(true)
     - COBA await getChunkDetail(childId)
     - JIKA component masih mounted: setDetail(data)
     - JIKA error: setDetail(null)
     - SELALU: setIsLoading(false)
     - Cleanup: set isMounted = false

5. NAVIGATION HANDLERS
   - handleBack(): router.push('/admin/dashboard')

6. LOADING STATE RENDERING
   - JIKA isLoading:
     - Full-screen centered loading dengan Loader2 spinner
     - Purple color styling sesuai theme

7. ERROR STATE RENDERING  
   - JIKA tidak ada detail setelah loading:
     - Empty state dengan error message
     - "Chunk Tidak Ditemukan" dengan childId
     - Back button untuk return ke dashboard

8. MAIN UI STRUCTURE
   - VIEW CONTAINER: "view active"
   - HEADER: main-header
     - Mobile hamburger menu button
     - Title: "Edit Child Chunk"
     - Info toggle button untuk mobile info panel
   
   - CONTENT: content-scroll
     - Breadcrumb navigation bar
     - Edit shell dengan three-column layout

9. BREADCRUMB NAVIGATION
   - Back button dengan ChevronLeft icon
   - Hierarchical breadcrumbs:
     - Domain (Source) -> Section -> Parent Title -> Child ID
     - Clickable breadcrumb items untuk navigation
     - Current item styling untuk active state

10. THREE-COLUMN LAYOUT
    - LEFT COLUMN: edit-tree-col
      - Knowledge tree navigation
      - Search input untuk tree filtering
      - KnowledgeTreeColumn component
    
    - MIDDLE COLUMN: edit-main-col
      - Scrollable content area
      - Chunk title dan pages display
      - ChunkEditForm component dengan full layout
    
    - RIGHT COLUMN: edit-info-col (mobile collapsible)
      - Info panel dengan chunk metadata
      - Conditional visibility berdasarkan showInfoPanel

11. INFO PANEL CONTENT
    - Chunk Information fields:
      - CHILD ID
      - PARENT CHUNK (title)
      - DOMAIN
      - SOURCE  
      - SECTION
      - PAGES
    - Separator line
    - EMBEDDING STATUS dengan badge styling:
      - Success: green badge
      - Stale: yellow badge  
      - Failed: red badge
      - Pending: blue badge
    - Last embedded timestamp display

12. MOBILE RESPONSIVENESS
    - Overlay untuk mobile info panel
    - Click outside to close info panel
    - Responsive column layout
    - Touch-friendly navigation elements

13. FORM INTEGRATION
    - ChunkEditForm dengan layout="full"
    - onSaved callback: update detail state
    - onDeleted callback: navigate back ke dashboard
    - Real-time form updates dengan optimistic UI

14. SEARCH FUNCTIONALITY
    - Tree search dengan real-time filtering
    - Search state passed ke KnowledgeTreeColumn
    - No debouncing untuk immediate results
```

**Editor Features:**
- Dynamic route dengan type-safe params handling
- Three-column responsive layout
- Real-time chunk editing dengan form integration
- Hierarchical breadcrumb navigation
- Mobile-optimized dengan collapsible panels
- Comprehensive chunk metadata display
- Loading dan error states dengan proper UX