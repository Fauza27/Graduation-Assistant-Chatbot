import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface ChatMessage {
  role: 'user' | 'bot';
  text: string;
  sources?: string[];
}

interface AppState {
  session_id: string | null;
  messages: ChatMessage[];
  hasHydrated: boolean;
  
  // Actions
  addMessage: (role: 'user' | 'bot', text: string, sources?: string[]) => void;
  setMessages: (messages: ChatMessage[]) => void;
  resetSession: () => void;
  setHydrated: (state: boolean) => void;
  setSessionId: (id: string) => void;
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
    }),
    {
      name: 'wcd-chat-storage', // key in localStorage
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.setHydrated(true);
        }
      },
    }
  )
);
