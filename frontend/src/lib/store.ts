import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface CitationSource {
  title?: string;
  section?: string;
  parent_id?: string;
  score?: number;
  pages?: number[];
}
export type MessageRole = 'user' | 'bot';
export interface ChatMessage {
  role: MessageRole;
  text: string;
  sources?: (CitationSource | string)[];
}

interface AppState {
  session_id: string | null;
  messages: ChatMessage[];
  hasHydrated: boolean;
  isDocPanelOpen: boolean;
  activeDoc: string | null;
  isSidebarOpen: boolean;
  isSidebarCollapsed: boolean;
}

interface AppActions {
  addMessage: (role: MessageRole, text: string, sources?: (CitationSource | string)[]) => void;
  setMessages: (messages: ChatMessage[]) => void;
  resetSession: () => void;
  setHydrated: (state: boolean) => void;
  setSessionId: (id: string) => void;
  setDocPanelOpen: (isOpen: boolean) => void;
  setActiveDoc: (docUrl: string | null) => void;
  openDocument: (docUrl: string | null) => void;
  setSidebarOpen: (isOpen: boolean) => void;
  setSidebarCollapsed: (isCollapsed: boolean) => void;
  toggleSidebar: () => void;
}

export type AppStore = AppState & AppActions;

const initialState: AppState = {
  session_id: null,
  messages: [],
  hasHydrated: false,
  isDocPanelOpen: false,
  activeDoc: null,
  isSidebarOpen: true,
  isSidebarCollapsed: false,
};

export const useAppStore = create<AppStore>()(
  persist(
    (set) => ({
      ...initialState,

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

      setHydrated: (hasHydrated) => set({ hasHydrated }),
      setSessionId: (session_id) => set({ session_id }),

      setDocPanelOpen: (isDocPanelOpen) => set({ isDocPanelOpen }),
      setActiveDoc: (activeDoc) => set({ activeDoc }),
      openDocument: (activeDoc) => set({ isDocPanelOpen: true, activeDoc }),
      setSidebarOpen: (isSidebarOpen) => set({ isSidebarOpen, isSidebarCollapsed: !isSidebarOpen }),
      setSidebarCollapsed: (isSidebarCollapsed) => set({ isSidebarCollapsed, isSidebarOpen: !isSidebarCollapsed }),
      toggleSidebar: () => set((state) => ({ 
        isSidebarOpen: !state.isSidebarOpen, 
        isSidebarCollapsed: state.isSidebarOpen 
      })),
    }),
    {
      name: 'wcd-chat-storage',
      partialize: (state) => ({
        session_id: state.session_id,
        messages: state.messages,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated(true);
      },
    }
  )
);
