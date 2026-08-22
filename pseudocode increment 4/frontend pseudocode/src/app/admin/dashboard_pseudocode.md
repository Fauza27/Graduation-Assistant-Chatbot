# Pseudocode: Admin Dashboard Page

## File: `app/admin/dashboard/page.tsx`

```markdown
ALGORITMA ADMIN DASHBOARD PAGE (admin/dashboard/page.tsx)

1. COMPONENT SETUP
   - 'use client' directive
   - useState hooks untuk local state
   - useRouter untuk navigation  
   - Lucide icons (Bell, Search, Menu)
   - useAdminStore untuk global state
   - Import semua admin components

2. STATE MANAGEMENT
   - Local State:
     - searchDoc: string (search filter untuk documents)
     - searchChild: string (search filter untuk child chunks) 
     - showNotif: boolean (notification dropdown toggle)
   - Global State (dari useAdminStore):
     - tree: KnowledgeTreeResponse | null
     - selectedChildId: string | null
     - selectedParentKey: string | null

3. HELPER FUNCTIONS
   - getSelectedParent(): ParentNode | null
     - Parse selectedParentKey untuk find active parent
     - Loop melalui tree structure: documents -> chapters -> parents
     - Match berdasarkan composite key: `${domain}-${source}-${section}-${parent_id}`
     - Return matching parent atau null

4. UI STRUCTURE LAYOUT
   - VIEW CONTAINER: "view active"
   - HEADER SECTION: main-header
     - Mobile hamburger menu button
     - Title: "Kelola Knowledge Base"
     - Description: "Kelola dokumen sumber, parent chunk, dan child chunk"
     - Notification dropdown dengan empty state
   
   - CONTENT SECTION: content-scroll
     - StatGrid component (summary statistics)
     - KB Browser: kb-browser container

5. KB BROWSER STRUCTURE
   - KB COLUMNS: kb-columns (two-column layout)
   
   - COLUMN 1: Struktur Dokumen
     - Header dengan step chip "1"
     - Title: "Struktur Dokumen"
     - Hint: "Pilih dokumen, lalu parent chunk di dalamnya"
     - Search input untuk filter documents
     - KnowledgeTreeColumn component dengan tree data dan query filter
   
   - COLUMN 2: Child Chunk
     - Header dengan step chip "2" 
     - Title: "Child Chunk"
     - Hint: "Isi dari parent chunk yang sedang dipilih"
     - Search input untuk filter child chunks
     - ChildChunkColumn component dengan selected parent data
     - RelationDiagram component untuk visualisasi

   - SIDEBAR: ChunkDetailPanel
     - Slide-in panel untuk chunk details
     - Controlled by selectedChildId state

6. MOBILE RESPONSIVENESS
   - Hamburger menu untuk mobile navigation
   - Search inputs dengan responsive design
   - Column layout adapts untuk smaller screens
   - Touch-friendly interaction areas

7. NOTIFICATION SYSTEM
   - Bell icon dengan notification dot
   - Dropdown dengan empty state message
   - Toggle functionality dengan showNotif state
   - Click outside to close dropdown

8. SEARCH FUNCTIONALITY
   - Real-time search filtering untuk documents
   - Real-time search filtering untuk child chunks
   - Search state passed ke child components
   - No debouncing - immediate filtering

9. COMPONENT INTEGRATION
   - StatGrid: Display summary statistics dari tree
   - KnowledgeTreeColumn: Tree navigation dengan search
   - ChildChunkColumn: List child chunks dengan editor integration
   - RelationDiagram: Visual parent-child relationship
   - ChunkDetailPanel: Detailed view dan quick actions

10. NAVIGATION INTEGRATION
    - router.push untuk navigation ke chunk editor
    - onOpenEditor handler untuk chunk editing
    - Integrated dengan admin layout navigation
```

**Dashboard Features:**
- Two-step navigation (document selection -> chunk selection)
- Real-time search dan filtering
- Responsive design untuk desktop/mobile
- Component-based architecture dengan clear separation
- State management dengan Zustand integration
- Visual hierarchy dengan step indicators