'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { 
  Menu, 
  Search, 
  Trash2, 
  Clock, 
  MessageSquare 
} from 'lucide-react';

import { fetchSessions, fetchSessionDetails, deleteSession, SessionItem } from '../../../lib/api';
import { useAppStore } from '../../../lib/store';

// =============================================================================
// 1. TIPE DATA & HELPER FUNCTIONS
// =============================================================================

interface GroupedSessions {
  [key: string]: SessionItem[];
}

/**
 * Mengelompokkan sesi chat berdasarkan waktu kalender (Hari Ini, Kemarin, Lebih Lama)
 */
function groupSessionsByDate(sessions: SessionItem[]): GroupedSessions {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const groups: GroupedSessions = {
    'Hari Ini': [],
    'Kemarin': [],
    'Lebih Lama': [],
  };

  sessions.forEach((s) => {
    const d = new Date(s.last_access);
    const sessionDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());

    if (sessionDate.getTime() === today.getTime()) {
      groups['Hari Ini'].push(s);
    } else if (sessionDate.getTime() === yesterday.getTime()) {
      groups['Kemarin'].push(s);
    } else {
      groups['Lebih Lama'].push(s);
    }
  });

  return groups;
}

/**
 * Memformat tanggal/waktu sesuai kelompok waktu agar mudah dibaca pengguna
 */
function formatSessionTime(dateStr: string, groupLabel: string): string {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return '';

  if (groupLabel === 'Hari Ini') {
    return date.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
  }
  if (groupLabel === 'Kemarin') {
    return 'Kemarin';
  }
  return date.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
}

// =============================================================================
// 2. SUB-KOMPONEN TAMPILAN
// =============================================================================

/**
 * Komponen Item Percakapan dalam Daftar Riwayat
 */
function SessionHistoryItem({
  session,
  timeLabel,
  isOpening,
  onOpen,
  onDelete,
}: {
  session: SessionItem;
  timeLabel: string;
  isOpening: boolean;
  onOpen: (id: string) => void;
  onDelete: (e: React.MouseEvent, id: string) => void;
}) {
  return (
    <div
      className="riwayat-item"
      onClick={() => onOpen(session.session_id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter') onOpen(session.session_id);
      }}
      style={{ cursor: 'pointer' }}
    >
      {/* Ikon pesan atau spinner saat sedang membuka sesi */}
      <div className="doc-icon">
        {isOpening ? (
          <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
        ) : (
          <MessageSquare size={18} />
        )}
      </div>

      {/* Judul percakapan */}
      <div className="riwayat-title">{session.title}</div>

      {/* Waktu percakapan */}
      <div className="riwayat-time">{timeLabel}</div>

      {/* Tombol hapus percakapan */}
      <button
        type="button"
        className="riwayat-delete-btn"
        onClick={(e) => onDelete(e, session.session_id)}
        title="Hapus percakapan ini"
        aria-label="Hapus percakapan ini"
      >
        <Trash2 className="icon-sm" size={16} />
      </button>
    </div>
  );
}

// =============================================================================
// 3. KOMPONEN UTAMA (RiwayatPage)
// =============================================================================

export default function RiwayatPage() {
  const router = useRouter();

  // --- A. STATE GLOBAL (Zustand Store) ---
  const activeSessionId = useAppStore((state) => state.session_id);
  const isSidebarOpen = useAppStore((state) => state.isSidebarOpen);
  const setSessionId = useAppStore((state) => state.setSessionId);
  const setMessages = useAppStore((state) => state.setMessages);
  const resetSession = useAppStore((state) => state.resetSession);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);

  // --- B. STATE LOKAL ---
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // --- C. LIFECYCLE / EFEK: Ambil Data Riwayat dari Backend ---
  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await fetchSessions();
        setSessions(data.sessions || []);
      } catch (error) {
        console.error('Error saat mengambil riwayat chat:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  // --- D. EVENT HANDLERS ---

  // Membuka percakapan lama dan mengarahkan pengguna ke halaman Chat
  const handleOpenSession = async (id: string) => {
    if (openingId) return;
    setOpeningId(id);

    try {
      const details = await fetchSessionDetails(id);
      if (details.messages) {
        setSessionId(id);
        setMessages(details.messages);
        router.push('/chat');
      }
    } catch (error) {
      console.error('Gagal membuka percakapan:', error);
      alert('Gagal memuat sesi percakapan ini.');
      setOpeningId(null);
    }
  };

  // Menghapus sesi tertentu dari daftar
  const handleDeleteSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation(); // Mencegah item terbuka saat tombol hapus diklik
    if (!window.confirm('Apakah Anda yakin ingin menghapus percakapan ini dari riwayat?')) {
      return;
    }

    try {
      await deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.session_id !== id));
      // Jika sesi yang dihapus adalah sesi aktif saat ini, reset state sesi
      if (activeSessionId === id) {
        resetSession();
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Terjadi kesalahan saat menghapus.';
      alert(`Gagal menghapus percakapan: ${errorMessage}`);
    }
  };

  // --- E. FILTERING & PENGELOMPOKAN DATA ---

  // Filter daftar sesi berdasarkan kata kunci pencarian
  const filteredSessions = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return sessions;
    return sessions.filter((s) => s.title.toLowerCase().includes(query));
  }, [sessions, searchQuery]);

  // Kelompokkan sesi yang sudah difilter ke dalam 'Hari Ini', 'Kemarin', 'Lebih Lama'
  const groupedSessions = useMemo(() => {
    return groupSessionsByDate(filteredSessions);
  }, [filteredSessions]);

  // --- F. RENDER TAMPILAN ---
  return (
    <>
      {/* 1. Header Halaman */}
      <div className="main-header">
        <button
          type="button"
          className="icon-btn sidebar-toggle-btn"
          onClick={toggleSidebar}
          aria-label={isSidebarOpen ? 'Tutup Sidebar' : 'Buka Sidebar'}
          title={isSidebarOpen ? 'Tutup Sidebar' : 'Buka Sidebar'}
        >
          <Menu className="icon" size={20} />
        </button>
        <h2 className="h2">Riwayat Chat</h2>
      </div>

      {/* 2. Isi Halaman Riwayat */}
      <section className="view active" style={{ display: 'flex' }}>
        <div className="riwayat-body">
          {/* Kolom Pencarian */}
          <div className="input-field riwayat-search" style={{ marginBottom: 18 }}>
            <Search className="icon" size={18} style={{ color: 'var(--gray-400)' }} />
            <input
              type="text"
              placeholder="Cari percakapan..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              autoComplete="off"
            />
          </div>

          {/* Kondisi 1: Sedang Memuat Data */}
          {isLoading ? (
            <div style={{ textAlign: 'center', marginTop: '40px' }}>
              <div className="spinner" />
            </div>
          ) : /* Kondisi 2: Belum Ada Riwayat Sama Sekali */
          sessions.length === 0 ? (
            <div className="empty-state">
              <div className="empty-badge">
                <Clock size={32} />
              </div>
              <h3 className="h3">Belum Ada Riwayat</h3>
              <p className="body2">Percakapan Anda dengan asisten akan otomatis tersimpan di sini.</p>
            </div>
          ) : /* Kondisi 3: Hasil Pencarian Tidak Ditemukan */
          filteredSessions.length === 0 ? (
            <p className="body2" style={{ color: 'var(--gray-400)', textAlign: 'center', padding: '24px 0' }}>
              Tidak ada percakapan yang cocok dengan pencarian.
            </p>
          ) : (
            /* Kondisi 4: Render Daftar Berdasarkan Kelompok Tanggal */
            Object.entries(groupedSessions).map(([label, list]) => {
              if (list.length === 0) return null;
              return (
                <div key={label} className="riwayat-group">
                  <div className="riwayat-group-label">{label}</div>
                  {list.map((session, idx) => (
                    <SessionHistoryItem
                      key={session.session_id || idx}
                      session={session}
                      timeLabel={formatSessionTime(session.last_access, label)}
                      isOpening={openingId === session.session_id}
                      onOpen={handleOpenSession}
                      onDelete={handleDeleteSession}
                    />
                  ))}
                </div>
              );
            })
          )}
        </div>
      </section>
    </>
  );
}

