ALGORITMA HALAMAN CHAT

1. IMPORTS & DEPENDENCIES
   - useState, useEffect, useRef dari React
   - useAppStore, CitationSource dari lib/store
   - sendChatMessage, deleteSession dari lib/api
   - ReactMarkdown untuk rendering bot responses
   - DOCUMENTS dari lib/documentSources untuk citation handling

2. STATE MANAGEMENT
   - Local State: inputValue (string), isLoading (boolean), menuOpen (boolean)
   - Global State dari useAppStore: session_id, messages, hasHydrated
   - Ref: chatScrollRef untuk auto-scroll behavior

3. USEEFFECTS
   - Rehydration & Empty session initialization:
     - JIKA hasHydrated = true DAN session_id = null: call resetSession()
   - Auto scroll to bottom:
     - Setiap kali messages atau isLoading berubah: scroll chatScrollRef ke bottom

4. HANDLER FUNCTIONS
   - handleSend(): 
     - Validate input (trim, session_id exists)
     - Add user message to store
     - Clear input, set loading
     - Call sendChatMessage API
     - Add bot response dengan sources
     - Handle errors dengan proper error typing (Error | unknown)
   
   - handleKeyDown(e: React.KeyboardEvent):
     - JIKA Enter pressed DAN !shiftKey: prevent default, call handleSend()
   
   - handleDeleteSession():
     - Show confirmation dialog dengan window.confirm
     - Call deleteSession API dengan session_id
     - Call resetSession() untuk clear state
     - Handle errors dengan alert dan proper error typing

5. CITATION HANDLING
   - handleCitationClick(src: CitationSource | string):
     - Convert string sources ke CitationSource object
     - Determine document domain berdasarkan parent_id analysis (kkp, pi, non-skripsi, skripsi)
     - Find document URL dari DOCUMENTS array berdasarkan domain
     - Build PDF URL dengan #page=N navigation (primary) atau #search= fallback
     - Call openDocument() dari store untuk show document panel

6. RENDER LOGIC
   - Hydration guard: return null jika !hasHydrated (prevent flicker)
   - Header: Title "Chat" dengan dropdown menu (kebab icon) untuk delete session
   - Main content dengan conditional classes (chat-empty jika no messages):
     - JIKA messages.length = 0: Empty state dengan welcome message, icon, suggestion chips
     - JIKA ada messages: Map melalui messages array:
       - User messages: bubble styling dengan purple background
       - Bot messages: ReactMarkdown rendering tanpa bubble, dengan avatar
       - Citations: Map sources dengan citation cards (clickable dengan handleCitationClick)
   - Loading state: Typing dots animation saat isLoading
   - Composer: Input field dengan suggestion chips, send button, keyboard handling, hint text

7. RESPONSIVE & UX FEATURES
   - Auto-resize input field
   - Keyboard shortcuts (Enter to send, Shift+Enter for newline)
   - Mobile-friendly touch interactions
   - Auto scroll behavior management
   - Citation click handling dengan PDF navigation
   - Error handling dengan user-friendly messages
   - Proper TypeScript typing untuk error objects
