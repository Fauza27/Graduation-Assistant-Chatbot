# Pseudocode: Admin Components Overview

## Comprehensive Admin Components (components/admin/*)

```markdown
ALGORITMA ADMIN COMPONENTS ECOSYSTEM

1. CORE FORM COMPONENTS

## ChunkEditForm.tsx
ALGORITMA CHUNK EDIT FORM (ChunkEditForm.tsx)
- Props: {chunk, onSaved, onDeleted, layout?: 'sidebar' | 'full'}
- State Management:
  - activeTab: 'metadata' | 'content'
  - Draft states: titleDraft, pagesDraft, contentDraft
  - Loading states: isSaving
  - Modal states: showReembedModal, showDeleteModal
- Key Functions:
  - handleSave(): Validate changes, call saveChunk API, update tree
  - handleDelete(): Call deleteChunk API, update tree, navigation
  - showToast(): Global toast notifications untuk feedback
- UI Features:
  - Tabbed interface untuk metadata vs content editing
  - Real-time draft synchronization
  - Save/delete/re-embed action buttons
  - Mengadaptasi layout secara dinamis (sidebar vs full-page)
  - Textarea stretch (flex: 1) untuk editor konten luas

2. NAVIGATION COMPONENTS

## KnowledgeTreeColumn.tsx  
ALGORITMA KNOWLEDGE TREE NAVIGATION (KnowledgeTreeColumn.tsx)
- Props: {tree, query} 
- Features:
  - Hierarchical tree rendering (Domain -> Chapter -> Parent)
  - Search filtering dengan highlight
  - Expandable/collapsible sections
  - Click handlers untuk parent selection
  - Empty states dan loading states
- Structure:
  - Document groups dengan domain badges
  - Chapter sections dengan parent counts
  - Parent items dengan child counts dan metadata

## ChildChunkColumn.tsx
ALGORITMA CHILD CHUNK LIST (ChildChunkColumn.tsx)  
- Props: {parent, query, onOpenEditor}
- Features:
  - Filtered child chunk listing
  - Search highlighting
  - Embedding status badges
  - Click handlers untuk chunk selection
  - Editor navigation integration
- Status Indicators:
  - Visual badges untuk embedding status
  - Page number displays
  - Parent context information

3. DETAIL PANELS

## ChunkDetailPanel.tsx
ALGORITMA CHUNK DETAIL PANEL (ChunkDetailPanel.tsx)
- Props: {childId, isMobileShell?: boolean}
- Features:
  - Slide-in panel behavior
  - Real-time chunk data loading
  - Metadata display dengan formatting
  - Quick action buttons
  - Mobile responsive dengan overlay
- Content Sections:
  - Chunk identification info
  - Parent relationship context
  - Embedding status tracking
  - Action buttons untuk edit/delete

## StatGrid.tsx  
ALGORITMA DASHBOARD STATISTICS (StatGrid.tsx)
- Props: {summary}
- Features:
  - Grid layout untuk statistics cards
  - Animated counters untuk numbers
  - Icon representations untuk different metrics
  - Responsive card sizing
- Metrics Display:
  - Total documents count
  - Total parents count  
  - Total children count
  - Last updated timestamp

4. INTERACTIVE COMPONENTS

## ReembedStatusModal.tsx
ALGORITMA RE-EMBED STATUS MODAL (ReembedStatusModal.tsx)
- Props: {childId, isOpen, onClose}
- Features:
  - Modal overlay dengan backdrop
  - Real-time status polling
  - Progress indicators
  - Error handling dan retry options
- Status Display:
  - Pending/Processing/Success/Failed states
  - Progress animations
  - Error message display
  - Action buttons untuk retry

## DeleteConfirmModal.tsx
ALGORITMA DELETE CONFIRMATION (DeleteConfirmModal.tsx)
- Props: {isOpen, onClose, onConfirm, chunkTitle}
- Features:
  - Warning modal dengan destructive styling
  - Confirmation flow dengan typing verification
  - Loading states during deletion
  - Error handling
- Safety Features:
  - Clear warning text
  - Confirmation button styling
  - Cancel option
  - Loading prevention untuk double-clicks

5. LAYOUT COMPONENTS

## AdminSidebar.tsx
ALGORITMA ADMIN SIDEBAR NAVIGATION (AdminSidebar.tsx)
- Props: {onCloseMobile}
- Features:
  - Navigation menu struktur
  - Active route highlighting  
  - User profile display
  - Logout functionality
  - Mobile collapse behavior
- Navigation Items:
  - Dashboard link
  - Knowledge base management
  - User profile section
  - Logout dengan confirmation

## MobileKnowledgeShell.tsx
ALGORITMA MOBILE KNOWLEDGE SHELL (MobileKnowledgeShell.tsx)
- Features:
  - Mobile-optimized layout
  - Swipe gestures untuk navigation
  - Collapsible panels
  - Touch-friendly interactions
- Mobile Adaptations:
  - Stacked layout instead of columns
  - Touch targets sizing
  - Rendering ChunkDetailPanel dengan `isMobileShell={true}` agar tidak konflik CSS
  - Responsive typography

6. VISUALIZATION COMPONENTS

## RelationDiagram.tsx
ALGORITMA PARENT-CHILD RELATION DIAGRAM (RelationDiagram.tsx)
- Props: {parent}
- Features:
  - Visual representation parent-child relationships via dinamis SVG (curve paths)
  - Interactive diagram dengan toggle collapse/expand
  - Render sesuai dengan format visual HTML mockup (titik ungu dengan path lengkung)
  - Responsive sizing
  - Accessibility support
- Diagram Elements:
  - Parent node representation
  - Child nodes dengan connections
  - Status indicators pada nodes
  - Hover states dan tooltips
```

**Component Architecture Features:**
- Modular design dengan clear separation of concerns
- Consistent prop interfaces dan TypeScript typing
- Responsive design dengan mobile-first approach
- Real-time state synchronization dengan Zustand
- Comprehensive error handling dan loading states
- Accessibility compliance dengan ARIA labels
- Performance optimization dengan React best practices