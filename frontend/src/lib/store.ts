import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface CitationSource {
  title?: string;
  section?: string;
  parent_id?: string;
  score?: number;
  pages?: number[];
}

export interface ChatMessage {
  role: 'user' | 'bot';
  text: string;
  sources?: (CitationSource | string)[];
}

interface AppState {
  session_id: string | null;
  messages: ChatMessage[];
  hasHydrated: boolean;
  
  // DocPanel State
  isDocPanelOpen: boolean;
  activeDoc: string | null;
  
  // Actions
  addMessage: (role: 'user' | 'bot', text: string, sources?: string[]) => void;
  setMessages: (messages: ChatMessage[]) => void;
  resetSession: () => void;
  setHydrated: (state: boolean) => void;
  setSessionId: (id: string) => void;
  setDocPanelOpen: (isOpen: boolean) => void;
  setActiveDoc: (docUrl: string | null) => void;
  openDocument: (docUrl: string | null) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      session_id: null,
      messages: [],
      hasHydrated: false,

      addMessage: (role, text, sources) =>
        set((state) => ({
          messages: [...state.messages, { role, text, sources }],
        })),

      setMessages: (messages) => set({ messages }),

      resetSession: () =>
        set({
          session_id: crypto.randomUUID(),
          messages: [],
        }),

      setHydrated: (state) => set({ hasHydrated: state }),
      
      setSessionId: (id) => set({ session_id: id }),

      isDocPanelOpen: false,
      activeDoc: null,
      setDocPanelOpen: (isOpen) => set({ isDocPanelOpen: isOpen }),
      setActiveDoc: (docUrl) => set({ activeDoc: docUrl }),
      openDocument: (docUrl) => set({ isDocPanelOpen: true, activeDoc: docUrl }),
    }),
    {
      name: 'wcd-chat-storage', // key in localStorage
      partialize: (state) => ({ 
        session_id: state.session_id, 
        messages: state.messages, 
        hasHydrated: state.hasHydrated 
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.setHydrated(true);
        }
      },
    }
  )
);
