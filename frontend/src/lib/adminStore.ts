import { create } from 'zustand';
import { KnowledgeTreeResponse, EmbeddingStatus } from './adminTypes';
import { getKnowledgeTree } from './adminApi';

interface AdminState {
  tree: KnowledgeTreeResponse | null;
  isTreeLoading: boolean;
  selectedChildId: string | null;
  selectedParentKey: string | null;
  
  fetchTree: () => Promise<void>;
  selectChild: (childId: string | null, parentKey: string | null) => void;
  patchChunkInTree: (childId: string, updates: { embedding_status?: EmbeddingStatus }) => void;
  removeChunkFromTree: (childId: string, parentDeleted: boolean) => void;
}

export const useAdminStore = create<AdminState>((set, get) => ({
  tree: null,
  isTreeLoading: false,
  selectedChildId: null,
  selectedParentKey: null,

  fetchTree: async () => {
    set({ isTreeLoading: true });
    try {
      const data = await getKnowledgeTree();
      set({ tree: data, isTreeLoading: false });
    } catch (error) {
      console.error('Failed to fetch tree', error);
      set({ tree: null, isTreeLoading: false });
    }
  },

  selectChild: (childId, parentKey) => {
    set({ selectedChildId: childId, selectedParentKey: parentKey });
  },

  patchChunkInTree: (childId, updates) => {
    const { tree } = get();
    if (!tree) return;

    // Deep clone the tree to apply updates
    const newTree: KnowledgeTreeResponse = JSON.parse(JSON.stringify(tree));
    let found = false;

    for (const doc of newTree.documents) {
      for (const chap of doc.chapters) {
        for (const par of chap.parents) {
          const childIndex = par.children.findIndex(c => c.id === childId);
          if (childIndex !== -1) {
            par.children[childIndex] = { ...par.children[childIndex], ...updates };
            found = true;
            break;
          }
        }
        if (found) break;
      }
      if (found) break;
    }

    if (found) {
      set({ tree: newTree });
    }
  },

  removeChunkFromTree: (childId, parentDeleted) => {
    const { tree } = get();
    if (!tree) return;

    const newTree: KnowledgeTreeResponse = JSON.parse(JSON.stringify(tree));
    let found = false;

    for (const doc of newTree.documents) {
      for (let i = 0; i < doc.chapters.length; i++) {
        const chap = doc.chapters[i];
        
        for (let j = 0; j < chap.parents.length; j++) {
          const par = chap.parents[j];
          const childIndex = par.children.findIndex(c => c.id === childId);
          
          if (childIndex !== -1) {
            par.children.splice(childIndex, 1);
            newTree.summary.total_children = Math.max(0, newTree.summary.total_children - 1);
            
            if (parentDeleted) {
              chap.parents.splice(j, 1);
              newTree.summary.total_parents = Math.max(0, newTree.summary.total_parents - 1);
              
              // If chapter has no parents, remove chapter
              if (chap.parents.length === 0) {
                doc.chapters.splice(i, 1);
              }
            }
            
            found = true;
            break;
          }
        }
        if (found) break;
      }
      if (found) break;
    }

    if (found) {
      // Check if we need to clear selection
      const { selectedChildId } = get();
      if (selectedChildId === childId) {
        set({ tree: newTree, selectedChildId: null, selectedParentKey: null });
      } else {
        set({ tree: newTree });
      }
    }
  }
}));
