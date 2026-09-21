'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { getAuthToken, logout, refreshAuthToken } from '../../lib/auth';
import { useAppStore } from '../../lib/store';
import { deleteSession } from '../../lib/api';
import Link from 'next/link';
import { jwtDecode } from 'jwt-decode';
import { DOCUMENTS } from '../../lib/documentSources';

interface JWTPayload {
  exp: number;
  [key: string]: unknown;
}

export default function SiteLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [isDocSectionOpen, setIsDocSectionOpen] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const isDocPanelOpen = useAppStore((state) => state.isDocPanelOpen);
  const activeDoc = useAppStore((state) => state.activeDoc);
  const isSidebarOpen = useAppStore((state) => state.isSidebarOpen);
  const messages = useAppStore((state) => state.messages);
  const session_id = useAppStore((state) => state.session_id);
  const setDocPanelOpen = useAppStore((state) => state.setDocPanelOpen);
  const setActiveDoc = useAppStore((state) => state.setActiveDoc);
  const setSidebarOpen = useAppStore((state) => state.setSidebarOpen);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);
  const openDocument = useAppStore((state) => state.openDocument);
  const resetSession = useAppStore((state) => state.resetSession);

  // Authentication check & SSR hydration guard
  useEffect(() => {
    const checkAuth = async () => {
      let token = getAuthToken();
      try {
        if (!token) token = await refreshAuthToken();
        if (!token) throw new Error('No active session');

        let decoded = jwtDecode<JWTPayload>(token);
        if (decoded.exp * 1000 < Date.now()) {
          token = await refreshAuthToken();
          if (!token) throw new Error('Session expired');
          decoded = jwtDecode<JWTPayload>(token);
        }
        setIsAuthenticated(true);
      } catch {
        logout();
      }
    };

    checkAuth();
  }, [router]);

  // Initial responsive check: collapse sidebar on mobile screen width by default
  useEffect(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  }, [setSidebarOpen]);

  const handleNewChat = () => {
    resetSession();
    router.push('/chat');
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  };

  const handleDeleteChatMobile = async () => {
    if (!session_id) return;
    if (window.confirm('Apakah Anda yakin ingin menghapus percakapan ini?')) {
      try {
        await deleteSession(session_id);
      } catch (err) {
        console.warn('Delete session notice:', err);
      }
      resetSession();
    }
  };

  // Loading 
  if (!isAuthenticated) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg, #F9FAFB)' }}>
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="app">
      {/* SIDEBAR */}
      <aside className={`sidebar ${isSidebarOpen ? 'open' : 'collapsed'}`}>
        <div className="sidebar-header">
          <svg className="brand-mark" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
            <circle cx="20" cy="20" r="19" fill="#F5F1FC" stroke="#6D28D9" strokeWidth="1.4"/>
            <circle cx="20" cy="20" r="12.5" fill="none" stroke="#6D28D9" strokeWidth="1.4"/>
            <circle cx="20" cy="20" r="4" fill="#6D28D9"/>
          </svg>
          <div className="brand-text">
            <div className="b1">STMIK</div>
            <div className="b2">WIDYA CIPTA DHARMA</div>
          </div>
          <button 
            className="icon-btn sidebar-close" 
            onClick={() => setSidebarOpen(false)}
            aria-label="Tutup Sidebar"
            title="Tutup Sidebar"
          >
            <svg className="icon" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <button 
          className="btn-primary" 
          onClick={handleNewChat}
        >
          <svg className="icon-sm" viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Chat Baru
        </button>

        <nav className="sidebar-nav">
          <Link 
            href="/riwayat" 
            className={`nav-item ${pathname === '/riwayat' ? 'active' : ''}`} 
            onClick={() => {
              if (typeof window !== 'undefined' && window.innerWidth < 768) {
                setSidebarOpen(false);
              }
            }}
          >
            <svg className="icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 14"/></svg>
            Riwayat Chat
          </Link>

          <div className="nav-section">
            <button 
              className={`nav-section-header ${!isDocSectionOpen ? 'collapsed' : ''}`} 
              onClick={() => setIsDocSectionOpen(!isDocSectionOpen)}
              aria-expanded={isDocSectionOpen}
              aria-label="Toggle Dokumen Panduan"
            >
              DOKUMEN PANDUAN
              <svg className="icon-sm" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>
            </button>
            {isDocSectionOpen && (
              <div className="nav-section-list">
                {DOCUMENTS.map((doc) => (
                  <button
                    key={doc.id}
                    className={`doc-item ${activeDoc === doc.fileUrl && isDocPanelOpen ? 'active' : ''}`}
                    onClick={() => {
                      openDocument(doc.fileUrl);
                      if (typeof window !== 'undefined' && window.innerWidth < 768) {
                        setSidebarOpen(false);
                      }
                    }}
                    title={doc.title}
                  >
                    <span className="doc-icon">
                      <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    </span>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{doc.title}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </nav>

        <div className="sidebar-footer">
          <Link 
            href="/profil" 
            className={`nav-item ${pathname === '/profil' ? 'active' : ''}`} 
            onClick={() => {
              if (typeof window !== 'undefined' && window.innerWidth < 768) {
                setSidebarOpen(false);
              }
            }}
          >
            <svg className="icon" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            Profil
          </Link>
          <button className="nav-item" onClick={() => logout()}>
            <svg className="icon" viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            Logout
          </button>
        </div>
      </aside>
      <div className={`sidebar-overlay ${isSidebarOpen ? 'show' : ''}`} onClick={() => setSidebarOpen(false)} />

      {/* MAIN PANEL */}
      <main className={`main-panel ${isDocPanelOpen ? 'doc-open' : ''}`}>
        
        {/* MOBILE TOPBAR */}
        <div className="mobile-topbar">
          <button 
            className="icon-btn" 
            onClick={toggleSidebar}
            aria-label={isSidebarOpen ? "Tutup Menu" : "Buka Menu"}
          >
            <svg className="icon" viewBox="0 0 24 24"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>
          </button>
          <h1>{pathname === '/riwayat' ? 'Riwayat Chat' : pathname === '/profil' ? 'Profil' : 'Asisten WCD'}</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            {pathname === '/chat' && messages.length > 0 && (
              <button 
                className="icon-btn" 
                onClick={handleDeleteChatMobile}
                aria-label="Hapus Percakapan"
                title="Hapus Percakapan"
                style={{ color: 'var(--danger, #DC2626)' }}
              >
                <svg className="icon-sm" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            )}
            <button 
              className="icon-btn" 
              onClick={handleNewChat}
              aria-label="Chat Baru"
              title="Chat Baru"
            >
              <svg className="icon" viewBox="0 0 24 24"><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 1 1 17 .5z"/><line x1="12" y1="8.5" x2="12" y2="13.5"/><line x1="9.5" y1="11" x2="14.5" y2="11"/></svg>
            </button>
          </div>
        </div>

        {/* CHILDREN */}
        {children}

        {/* MOBILE BOTTOM NAV */}
        <nav className="bottom-nav">
          <div className="bottom-nav-inner">
            <Link href="/chat" className={`bn-item ${pathname === '/chat' ? 'active' : ''}`}>
              <svg viewBox="0 0 24 24" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-4.5 7.5 8.5 8.5 0 0 1-9-1L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 8.5-8.5h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
              <span>Chat</span>
            </Link>
            <Link href="/riwayat" className={`bn-item ${pathname === '/riwayat' ? 'active' : ''}`}>
              <svg viewBox="0 0 24 24" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 14"/></svg>
              <span>Riwayat</span>
            </Link>
            <Link href="/profil" className={`bn-item ${pathname === '/profil' ? 'active' : ''}`}>
              <svg viewBox="0 0 24 24" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              <span>Profil</span>
            </Link>
          </div>
        </nav>
      </main>

      {/* DOCUMENT PANEL */}
      <aside className={`doc-panel ${isDocPanelOpen ? 'open' : ''}`}>
        <div className="doc-panel-inner">
          <div className="doc-panel-header">
            {activeDoc ? (
              <button 
                className="icon-btn" 
                onClick={() => setActiveDoc(null)} 
                title="Kembali ke Daftar Dokumen"
                aria-label="Kembali ke Daftar Dokumen"
              >
                <svg className="icon" viewBox="0 0 24 24"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
              </button>
            ) : (
              <button 
                className="icon-btn mobile-only" 
                onClick={() => setDocPanelOpen(false)}
                aria-label="Tutup Dokumen"
              >
                <svg className="icon" viewBox="0 0 24 24"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
              </button>
            )}
            
            <h3 className="h3">Dokumen Panduan</h3>
            
            <div style={{ display: 'flex', gap: '4px' }}>
              {activeDoc && (
                <a href={activeDoc} target="_blank" rel="noopener noreferrer" className="icon-btn" title="Buka di Tab Baru" aria-label="Buka di Tab Baru">
                  <svg className="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                </a>
              )}
              <button 
                className="icon-btn" 
                onClick={() => setDocPanelOpen(false)}
                aria-label="Tutup Dokumen"
              >
                <svg className="icon" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </div>
          
          <div className="doc-page-scroll" style={{ padding: activeDoc ? '0' : '20px 14px' }}>
            {activeDoc ? (
              <iframe 
                key={activeDoc}
                src={activeDoc} 
                style={{ width: '100%', height: '100%', border: 'none', minHeight: 'calc(100vh - 70px)' }}
                title="PDF Viewer"
              />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <p className="body2" style={{ color: 'var(--gray-500)', marginBottom: '16px' }}>
                  Pilih dokumen panduan untuk dibaca langsung di sini.
                </p>
                {DOCUMENTS.map((doc) => (
                  <button 
                    key={doc.id}
                    className="doc-item" 
                    onClick={() => setActiveDoc(doc.fileUrl)}
                    style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: '12px', 
                      padding: '16px', 
                      background: '#F9FAFB', 
                      border: '1px solid #E5E7EB', 
                      borderRadius: '8px',
                      cursor: 'pointer',
                      textAlign: 'left'
                    }}
                  >
                    <div className="doc-icon" style={{ flexShrink: 0, color: 'var(--primary-600)' }}>
                      <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                    </div>
                    <div style={{ flexGrow: 1 }}>
                      <div className="body1" style={{ fontWeight: 600, color: 'var(--gray-900)' }}>{doc.title}</div>
                    </div>
                    <svg viewBox="0 0 24 24" width="20" height="20" stroke="var(--gray-400)" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </aside>
      <div className={`doc-overlay ${isDocPanelOpen ? 'show' : ''}`} onClick={() => setDocPanelOpen(false)} />
    </div>
  );
}
