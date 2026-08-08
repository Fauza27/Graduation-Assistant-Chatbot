'use client';

import { useState, useEffect, useRef } from 'react';
import { useAppStore, CitationSource } from '../../../lib/store';
import { sendChatMessage, deleteSession } from '../../../lib/api';
import ReactMarkdown from 'react-markdown';
import { DOCUMENTS } from '../../../lib/documentSources';

export default function ChatPage() {
  const { session_id, messages, hasHydrated, addMessage, resetSession, openDocument } = useAppStore();
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  // Rehydration & Empty session initialization
  useEffect(() => {
    if (hasHydrated && !session_id) {
      resetSession();
    }
  }, [hasHydrated, session_id, resetSession]);

  // Auto scroll to bottom
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!inputValue.trim() || !session_id) return;
    const currentInput = inputValue;
    setInputValue('');
    addMessage('user', currentInput);
    setIsLoading(true);

    try {
      const response = await sendChatMessage(currentInput, session_id);
      addMessage('bot', response.answer || '...', response.sources || []);
    } catch (err: any) {
      addMessage('bot', `**Error:** ${err.message || 'Gagal terhubung ke server.'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleDeleteSession = async () => {
    if (!session_id) return;
    if (window.confirm('Apakah Anda yakin ingin menghapus percakapan ini?')) {
      try {
        await deleteSession(session_id);
        resetSession();
        setMenuOpen(false);
      } catch (err: any) {
        alert(`Gagal menghapus percakapan: ${err.message}`);
      }
    }
  };

  const handleCitationClick = (src: CitationSource | string) => {
    const srcObj = typeof src === 'string' ? { title: src } : src;
    let domain = 'skripsi'; // default
    if (srcObj.parent_id) {
      const pid = srcObj.parent_id.toLowerCase();
      if (pid.includes('kkp')) domain = 'kkp';
      else if (pid.includes('non-skripsi') || pid.includes('nonskripsi')) domain = 'non-skripsi';
      else if (pid.includes('pi')) domain = 'pi';
    }
    let docUrl = DOCUMENTS.find(d => d.id === domain)?.fileUrl || DOCUMENTS[2].fileUrl;
    
    // Tambahkan parameter pencarian ke URL PDF agar langsung menuju teks yang relevan
    const searchTerm = srcObj.title || srcObj.section || srcObj.parent_id;
    if (searchTerm) {
      // Ambil kata-kata penting (misal 5-8 kata) dan hindari penggunaan tanda kutip literal 
      // agar tidak menghalangi matching apabila teks tidak 100% identik.
      const query = searchTerm.split(' ').slice(0, 8).join(' ');
      docUrl += `#search=${encodeURIComponent(query)}`;
    }
    
    console.log("Membuka dokumen:", docUrl);
    
    openDocument(docUrl);
  };

  // Prevent flicker during hydration
  if (!hasHydrated) return null;

  return (
    <>
      <div className="main-header">
        <h2 className="h2">Chat</h2>
        <div className="dropdown">
          <button 
            className="icon-btn header-icon-btn" 
            onClick={() => setMenuOpen(!menuOpen)}
          >
            <svg className="icon" viewBox="0 0 24 24"><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></svg>
          </button>
          {menuOpen && (
            <div className="dropdown-menu show" style={{ right: 20 }}>
              <button className="danger" onClick={handleDeleteSession}>
                <svg className="icon-sm" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                Hapus Percakapan
              </button>
            </div>
          )}
        </div>
      </div>

      <section className={`view active ${messages.length === 0 ? 'chat-empty' : ''}`} style={{ display: 'flex' }}>
        <div className="chat-scroll" ref={chatScrollRef}>
          <div className="chat-inner">
            {messages.length === 0 ? (
              <div className="empty-state">
                <div className="empty-badge">
                  <svg viewBox="0 0 24 24"><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 1 1 17 .5z"/><line x1="12" y1="8.5" x2="12" y2="13.5"/><line x1="9.5" y1="11" x2="14.5" y2="11"/></svg>
                </div>
                <h3 className="h3">Mulai percakapan baru</h3>
                <p className="body2">Tanyakan apa saja seputar PI, KKP, Skripsi, atau Jalur Lulus Non Skripsi.</p>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} className={`msg-row ${msg.role}`}>
                  <div className="msg-col">
                    {msg.role === 'user' ? (
                      <div className="bubble">
                        {msg.text}
                      </div>
                    ) : (
                      <>
                        <div className="bot-text">
                          <ReactMarkdown>{msg.text}</ReactMarkdown>
                        </div>
                        {msg.sources && msg.sources.length > 0 && (
                          <>
                            <div className="bubble-label">Sumber Referensi</div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                              {msg.sources.map((src, i) => {
                                const srcObj = typeof src === 'string' ? { title: src, parent_id: '', section: '' } : src as CitationSource;
                                const displayTitle = srcObj.title || srcObj.section || 'Sumber Referensi';
                                return (
                                  <div key={i} className="citation-card" onClick={() => handleCitationClick(src)} style={{ cursor: 'pointer' }}>
                                    <div className="citation-icon">
                                      <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                                    </div>
                                    <div className="citation-text">
                                      <div className="citation-title">{displayTitle.substring(0, 60)}{displayTitle.length > 60 ? '...' : ''}</div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ))
            )}
            
            {isLoading && (
              <div className="msg-row bot">
                <div className="typing-dots">
                  <div className="dot"></div>
                  <div className="dot"></div>
                  <div className="dot"></div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="composer">
          <div className="composer-inner">
            <div className="suggestion-row">
              <button className="chip" onClick={() => setInputValue('Apa saja syarat pengajuan judul Skripsi?')}>
                <svg className="icon-sm" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                Syarat judul Skripsi
              </button>
              <button className="chip" onClick={() => setInputValue('Apa syarat pendaftaran KKP?')}>
                <svg className="icon-sm" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                Syarat pendaftaran KKP
              </button>
            </div>
            
            <div className="input-field">
              <input 
                type="text" 
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ketik pertanyaan Anda..." 
                disabled={isLoading}
              />
              <button className="send-btn" onClick={handleSend} disabled={!inputValue.trim() || isLoading}>
                <svg className="icon" viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
              </button>
            </div>
            <p className="caption composer-hint">Chatbot dapat membuat kesalahan. Jawaban selalu berdasarkan dokumen resmi.</p>
          </div>
        </div>
      </section>
    </>
  );
}
