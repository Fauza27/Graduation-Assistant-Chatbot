import { create } from 'zustand';
import { KnowledgeTreeResponse, EmbeddingStatus } from './adminTypes';
import { getKnowledgeTree } from './adminApi';

interface TreeIndex {
  [childId: string]: {
    docIdx: number;
    chapIdx: number;
    parentIdx: number;
    childIdx: number;
  };
}

interface AdminState {
  tree: KnowledgeTreeResponse | null;
  treeIndex: TreeIndex;
  isTreeLoading: boolean;
  selectedChildId: string | null;
  selectedParentKey: string | null;
  
  fetchTree: () => Promise<void>;
  selectChild: (childId: string | null, parentKey: string | null) => void;
  patchChunkInTree: (childId: string, updates: { embedding_status?: EmbeddingStatus }) => void;
  removeChunkFromTree: (childId: string, parentDeleted: boolean) => void;
}

// Helper function to build index for O(1) lookups
function buildTreeIndex(tree: KnowledgeTreeResponse): TreeIndex {
  const index: TreeIndex = {};
  
  tree.documents.forEach((doc, docIdx) => {
    doc.chapters.forEach((chap, chapIdx) => {
      chap.parents.forEach((parent, parentIdx) => {
        parent.children.forEach((child, childIdx) => {
          index[child.id] = {
            docIdx,
            chapIdx,
            parentIdx,
            childIdx
          };
        });
      });
    });
  });
  
  return index;
}

export const useAdminStore = create<AdminState>((set, get) => ({
  tree: null,
  treeIndex: {},
  isTreeLoading: false,
  selectedChildId: null,
  selectedParentKey: null,

  fetchTree: async () => {
    set({ isTreeLoading: true });
    try {
      const data = await getKnowledgeTree();
      const index = buildTreeIndex(data);
      set({ tree: data, treeIndex: index, isTreeLoading: false });
    } catch (error) {
      console.error('Failed to fetch tree', error);
      set({ tree: null, treeIndex: {}, isTreeLoading: false });
    }
  },

  selectChild: (childId, parentKey) => {
    set({ selectedChildId: childId, selectedParentKey: parentKey });
  },

  patchChunkInTree: (childId, updates) => {
    const { tree, treeIndex } = get();
    if (!tree || !treeIndex[childId]) return;

    // O(1) direct access using index - no deep clone or loops needed
    const location = treeIndex[childId];
    const targetChild = tree.documents[location.docIdx]
      .chapters[location.chapIdx]
      .parents[location.parentIdx]
      .children[location.childIdx];

    // Update child directly (mutation is fine for Zustand)
    Object.assign(targetChild, updates);

    // Trigger re-render by setting new reference
    set({ tree: { ...tree } });
  },

  removeChunkFromTree: (childId, parentDeleted) => {
    const { tree, treeIndex } = get();
    if (!tree || !treeIndex[childId]) return;

    // O(1) direct access using index
    const location = treeIndex[childId];
    const doc = tree.documents[location.docIdx];
    const chap = doc.chapters[location.chapIdx];
    const parent = chap.parents[location.parentIdx];
    
    // Remove child from parent
    parent.children.splice(location.childIdx, 1);
    tree.summary.total_children = Math.max(0, tree.summary.total_children - 1);
    
    // Update index for remaining children in same parent (shift indices)
    parent.children.forEach((child, newIdx) => {
      if (newIdx >= location.childIdx && treeIndex[child.id]) {
        treeIndex[child.id].childIdx = newIdx;
      }
    });
    
    // Remove from index
    delete treeIndex[childId];
    
    if (parentDeleted) {
      // Remove all children of this parent from index first
      parent.children.forEach(child => {
        delete treeIndex[child.id];
      });
      
      // Remove parent from chapter
      chap.parents.splice(location.parentIdx, 1);
      tree.summary.total_parents = Math.max(0, tree.summary.total_parents - 1);
      
      // Update index for remaining parents in same chapter (shift indices)
      chap.parents.forEach((remainingParent, newParentIdx) => {
        if (newParentIdx >= location.parentIdx) {
          remainingParent.children.forEach(child => {
            if (treeIndex[child.id]) {
              treeIndex[child.id].parentIdx = newParentIdx;
            }
          });
        }
      });
      
      // If chapter has no parents, remove chapter
      if (chap.parents.length === 0) {
        doc.chapters.splice(location.chapIdx, 1);
        
        // Update index for remaining chapters in same document (shift indices)
        doc.chapters.forEach((remainingChap, newChapIdx) => {
          if (newChapIdx >= location.chapIdx) {
            remainingChap.parents.forEach(remainingParent => {
              remainingParent.children.forEach(child => {
                if (treeIndex[child.id]) {
                  treeIndex[child.id].chapIdx = newChapIdx;
                }
              });
            });
          }
        });
      }
    }

    // Check if we need to clear selection
    const { selectedChildId } = get();
    if (selectedChildId === childId) {
      set({ tree: { ...tree }, treeIndex, selectedChildId: null, selectedParentKey: null });
    } else {
      set({ tree: { ...tree }, treeIndex });
    }
  }
}));
