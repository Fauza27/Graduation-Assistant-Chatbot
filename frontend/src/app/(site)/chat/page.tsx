'use client';

import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Send,
  Menu,
  Trash2,
  Copy,
  Check,
  ArrowDown,
  FileText,
  MessageSquarePlus,
  MoreVertical,
} from 'lucide-react';

import { useAppStore, CitationSource } from '../../../lib/store';
import { sendChatMessage, deleteSession } from '../../../lib/api';
import { DOCUMENTS } from '../../../lib/documentSources';

// =============================================================================
// 1. HELPER FUNCTIONS
// =============================================================================

/**
 * Membantu menentukan URL dokumen PDF dan halaman target berdasarkan sumber referensi (sitasi).
 */
function resolveCitationUrl(src: CitationSource | string): string {
  const srcObj = typeof src === 'string' ? { title: src } : src;
  let domain = 'skripsi'; // Domain default

  // Cek apakah parent_id mengarah ke kategori tertentu (KKP, Non-Skripsi, dsb)
  if (srcObj.parent_id) {
    const pid = srcObj.parent_id.toLowerCase();
    if (pid.includes('kkp')) domain = 'kkp';
    else if (pid.includes('non-skripsi') || pid.includes('nonskripsi'))
      domain = 'non-skripsi';
    else if (pid.includes('pi')) domain = 'pi';
  }

  // Ambil URL dokumen yang sesuai dari koleksi dokumen
  let docUrl =
    DOCUMENTS.find((d) => d.id === domain)?.fileUrl ||
    DOCUMENTS.find((d) => d.id === 'skripsi')?.fileUrl ||
    DOCUMENTS[0]?.fileUrl ||
    '';

  // Jika ada nomor halaman, tambahkan hash #page=X agar PDF otomatis membuka halaman tsb
  if (srcObj.pages && srcObj.pages.length > 0) {
    docUrl += `#page=${srcObj.pages[0]}`;
  } else {
    // Jika tidak ada nomor halaman spesifik, coba gunakan pencarian teks
    const searchTerm = srcObj.title || srcObj.section;
    if (searchTerm) {
      const query = searchTerm.split(' ').slice(0, 8).join(' ');
      docUrl += `#search=${encodeURIComponent(query)}`;
    }
  }

  return docUrl;
}

// Pertanyaan umum cepat (Quick Suggestions) saat percakapan masih baru/kosong
const QUICK_SUGGESTIONS = [
  {
    label: 'Syarat judul Skripsi',
    question: 'Apa saja syarat pengajuan judul Skripsi?',
  },
  { label: 'Syarat pendaftaran KKP', question: 'Apa syarat pendaftaran KKP?' },
  {
    label: 'Jalur Non Skripsi',
    question: 'Apa ketentuan Jalur Lulus Non Skripsi?',
  },
];

// =============================================================================
// 2. SUB-KOMPONEN TAMPILAN
// =============================================================================

/**
 * Komponen Card untuk satu sumber referensi (sitasi dokumen)
 */
function CitationCard({
  source,
  onClick,
}: {
  source: CitationSource | string;
  onClick: (src: CitationSource | string) => void;
}) {
  const srcObj = typeof source === 'string' ? { title: source } : source;
  const displayTitle = srcObj.title || srcObj.section || 'Sumber Referensi';
  const truncatedTitle =
    displayTitle.length > 60
      ? `${displayTitle.substring(0, 60)}...`
      : displayTitle;

  return (
    <button
      type="button"
      className="citation-card"
      onClick={() => onClick(source)}
      style={{ textAlign: 'left' }}
      aria-label={`Buka sumber: ${displayTitle}`}
    >
      <div className="citation-icon">
        <FileText size={16} />
      </div>
      <div className="citation-text">
        <div className="citation-title">{truncatedTitle}</div>
      </div>
    </button>
  );
}

/**
 * Komponen Tampilan Pesan Bot (Markdown + Referensi + Tombol Copy)
 */
function BotMessageItem({
  text,
  sources,
  onCitationClick,
  onCopy,
  isCopied,
}: {
  text: string;
  sources?: (string | CitationSource)[];
  onCitationClick: (src: CitationSource | string) => void;
  onCopy: () => void;
  isCopied: boolean;
}) {
  return (
    <div className="msg-row bot">
      <div className="msg-col">
        {/* Konten teks jawaban bot dirender menggunakan Markdown */}
        <div className="bot-text">
          <ReactMarkdown
            components={{
              a: ({ ...props }) => (
                <a {...props} target="_blank" rel="noopener noreferrer" />
              ),
            }}
          >
            {text}
          </ReactMarkdown>
        </div>

        {/* Daftar Sumber Dokumen (Sitasi) jika disediakan oleh AI */}
        {sources && sources.length > 0 && (
          <>
            <div className="bubble-label">Sumber Referensi</div>
            <div
              style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}
            >
              {sources.map((src, i) => (
                <CitationCard key={i} source={src} onClick={onCitationClick} />
              ))}
            </div>
          </>
        )}

        {/* Tombol aksi: Salin jawaban */}
        <div className="msg-actions">
          <button
            type="button"
            className={`msg-action-btn ${isCopied ? 'copied' : ''}`}
            onClick={onCopy}
            aria-label="Salin jawaban"
            title={isCopied ? 'Tersalin!' : 'Salin jawaban'}
          >
            {isCopied ? <Check size={14} /> : <Copy size={14} />}
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Komponen Tampilan Pesan Pengguna
 */
function UserMessageItem({ text }: { text: string }) {
  return (
    <div className="msg-row user">
      <div className="msg-col">
        <div className="bubble">{text}</div>
      </div>
    </div>
  );
}

// =============================================================================
// 3. KOMPONEN UTAMA (ChatPage)
// =============================================================================

export default function ChatPage() {
  // --- A. STATE DARI GLOBAL STORE (Zustand) ---
  const session_id = useAppStore((state) => state.session_id);
  const messages = useAppStore((state) => state.messages);
  const hasHydrated = useAppStore((state) => state.hasHydrated);
  const isSidebarOpen = useAppStore((state) => state.isSidebarOpen);
  const addMessage = useAppStore((state) => state.addMessage);
  const resetSession = useAppStore((state) => state.resetSession);
  const openDocument = useAppStore((state) => state.openDocument);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);

  // --- B. STATE LOKAL KOMPONEN ---
  const [inputValue, setInputValue] = useState('');
  const [inputError, setInputError] = useState<string | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [showScrollBottom, setShowScrollBottom] = useState(false);

  // --- C. REFS (Manipulasi DOM langsung) ---
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    },
    [],
  );

  // --- D. EFFECTS & LIFECYCLE ---

  // 1. Inisialisasi session jika aplikasi sudah hydrated tapi belum ada session_id
  useEffect(() => {
    if (hasHydrated && !session_id) {
      resetSession();
    }
  }, [hasHydrated, session_id, resetSession]);

  // 2. Tutup menu dropdown opsi jika pengguna mengklik area luar menu
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setMenuOpen(false);
      }
    };

    if (menuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [menuOpen]);

  // 3. Otomatis gulir ke bawah saat ada pesan baru atau bot sedang memproses
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  // --- E. EVENT HANDLERS (Fungsi Aksi Pengguna) ---

  // Memantau posisi scroll untuk memunculkan tombol 'kembali ke bawah'
  const handleScroll = () => {
    if (!chatScrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = chatScrollRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    setShowScrollBottom(messages.length > 0 && distanceFromBottom > 140);
  };

  // Menggulirkan area chat secara halus ke paling bawah
  const scrollToBottom = (smooth = true) => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTo({
        top: chatScrollRef.current.scrollHeight,
        behavior: smooth ? 'smooth' : 'auto',
      });
    }
  };

  // Mengirim pesan ke backend dan menambahkan respon ke tampilan
  const handleSend = async (overrideText?: string) => {
    const textToSend = (overrideText ?? inputValue).trim();
    if (!textToSend || !session_id || isLoading) return;
    if (textToSend.length < 3 || textToSend.length > 500) {
      setInputError('Pertanyaan harus terdiri dari 3 sampai 500 karakter.');
      return;
    }
    setInputError(null);

    // Bersihkan input teks & masukkan pesan user ke store tampilan
    setInputValue('');
    addMessage('user', textToSend);
    setIsLoading(true);

    try {
      // Panggil API chat backend
      const response = await sendChatMessage(textToSend, session_id);
      if (useAppStore.getState().session_id !== session_id) return;
      addMessage('bot', response.answer || '...', response.sources || []);

      if (response.error) {
        console.warn('Pemberitahuan layanan chat:', response.error);
      }
    } catch (err: unknown) {
      if (useAppStore.getState().session_id !== session_id) return;
      const errorMessage =
        err instanceof Error ? err.message : 'Gagal terhubung ke server.';
      addMessage('bot', `**Error:** ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Menangani penekanan tombol Enter pada kolom input
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Menyalin teks jawaban ke clipboard
  const handleCopy = async (text: string, idx: number) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyError(null);
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
      setCopiedIdx(idx);
      copyTimerRef.current = setTimeout(() => setCopiedIdx(null), 1500);
    } catch {
      setCopyError(
        'Jawaban belum bisa disalin otomatis. Pilih dan salin teks jawaban secara manual.',
      );
    }
  };

  // Menghapus riwayat sesi chat saat ini
  const handleDeleteSession = async () => {
    if (!session_id) return;
    if (window.confirm('Apakah Anda yakin ingin menghapus percakapan ini?')) {
      try {
        await deleteSession(session_id);
        resetSession();
        setMenuOpen(false);
      } catch (err: unknown) {
        const errorMessage =
          err instanceof Error ? err.message : 'Terjadi kesalahan';
        alert(`Gagal menghapus percakapan: ${errorMessage}`);
      }
    }
  };

  // Membuka modal dokumen PDF sesuai rujukan sitasi
  const handleCitationClick = (src: CitationSource | string) => {
    const docUrl = resolveCitationUrl(src);
    openDocument(docUrl);
  };

  // --- F. RENDER KONDISIONAL (Loading Hydration) ---
  if (!hasHydrated) {
    return (
      <section
        className="view active"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div className="spinner" />
      </section>
    );
  }

  // --- G. RENDER UTAMA ---
  return (
    <>
      {/* 1. HEADER HALAMAN (Desktop & Tablet) */}
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

        <h2 className="h2">Chat</h2>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            marginLeft: 'auto',
          }}
        >
          {/* Tombol Hapus Cepat (Hanya muncul jika ada pesan) */}
          {messages.length > 0 && (
            <button
              type="button"
              className="icon-btn"
              onClick={handleDeleteSession}
              aria-label="Hapus Percakapan"
              title="Hapus Percakapan"
              style={{ color: 'var(--danger, #DC2626)' }}
            >
              <Trash2 className="icon-sm" size={18} />
            </button>
          )}

          {/* Menu Opsi Dropdown */}
          <div className="dropdown" ref={dropdownRef}>
            <button
              type="button"
              className="icon-btn header-icon-btn"
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="Opsi Percakapan"
            >
              <MoreVertical className="icon" size={18} />
            </button>

            {menuOpen && (
              <div className="dropdown-menu show" style={{ right: 0 }}>
                <button
                  type="button"
                  className="danger"
                  onClick={handleDeleteSession}
                >
                  <Trash2 className="icon-sm" size={16} />
                  Hapus Percakapan
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 2. AREA KONTEN CHAT (Daftar Pesan & Form Input) */}
      <section
        id="view-chat"
        className={`view active ${messages.length === 0 ? 'chat-empty' : ''}`}
      >
        {/* Scrollable Container untuk Pesan */}
        <div
          className="chat-scroll"
          ref={chatScrollRef}
          onScroll={handleScroll}
        >
          <div className="chat-inner">
            {/* Tampilan Kosong (Empty State) jika belum ada obrolan */}
            {messages.length === 0 ? (
              <div className="empty-state">
                <div className="empty-badge">
                  <MessageSquarePlus size={32} />
                </div>
                <h3 className="h3">Mulai percakapan baru</h3>
                <p className="body2">
                  Tanyakan apa saja seputar PI, KKP, Skripsi, atau Jalur Lulus
                  Non Skripsi.
                </p>
              </div>
            ) : (
              // Perulangan Daftar Pesan
              messages.map((msg, idx) =>
                msg.role === 'user' ? (
                  <UserMessageItem key={idx} text={msg.text} />
                ) : (
                  <BotMessageItem
                    key={idx}
                    text={msg.text}
                    sources={msg.sources}
                    onCitationClick={handleCitationClick}
                    onCopy={() => handleCopy(msg.text, idx)}
                    isCopied={copiedIdx === idx}
                  />
                ),
              )
            )}

            {/* Animasi Indikator Mengetik (Typing Dots) saat Bot Loading */}
            {isLoading && (
              <div className="msg-row bot">
                <div className="typing-dots">
                  <div className="dot" />
                  <div className="dot" />
                  <div className="dot" />
                </div>
              </div>
            )}
          </div>

          {/* Tombol Mengambang: Scroll ke Paling Bawah */}
          {showScrollBottom && (
            <button
              type="button"
              className="scroll-bottom-btn show"
              onClick={() => scrollToBottom(true)}
              aria-label="Ke pesan terbaru"
            >
              <ArrowDown className="icon-sm" size={18} />
            </button>
          )}
        </div>

        {/* 3. BAGIAN COMPOSER (Input Pesan & Rekomendasi Pertanyaan) */}
        <div className="composer">
          <div className="composer-inner">
            {/* Kolom Input Teks & Tombol Kirim */}
            <div className="input-field">
              <input
                ref={inputRef}
                id="chat-input"
                name="chat-input"
                type="text"
                value={inputValue}
                onChange={(e) => {
                  setInputValue(e.target.value);
                  setInputError(null);
                }}
                maxLength={500}
                aria-label="Pertanyaan untuk chatbot"
                aria-describedby="chat-input-help"
                aria-invalid={Boolean(inputError)}
                onKeyDown={handleKeyDown}
                placeholder="Ketik pertanyaan Anda..."
                disabled={isLoading}
                autoComplete="off"
              />

              <button
                type="button"
                className="send-btn"
                onClick={() => handleSend()}
                disabled={inputValue.trim().length < 3 || isLoading}
                aria-label="Kirim Pesan"
              >
                <Send className="icon" size={18} />
              </button>
            </div>

            {/* Rekomendasi Pertanyaan Cepat (Chips) */}
            <div className="suggestion-row">
              {QUICK_SUGGESTIONS.map((item, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="chip"
                  disabled={isLoading}
                  onClick={() => handleSend(item.question)}
                >
                  <FileText className="icon-sm" size={14} />
                  {item.label}
                </button>
              ))}
            </div>

            {copyError && (
              <p
                className="caption composer-hint"
                role="alert"
                style={{ color: 'var(--danger)' }}
              >
                {copyError}
              </p>
            )}
            <p
              id="chat-input-help"
              className="caption composer-hint"
              role={inputError ? 'alert' : undefined}
              style={inputError ? { color: 'var(--danger)' } : undefined}
            >
              {inputError ||
                (inputValue.length >= 450
                  ? `${inputValue.length}/500 karakter`
                  : 'Gunakan pertanyaan yang jelas. Anda juga bisa bertanya lanjutan dalam percakapan yang sama.')}
            </p>
            <p className="caption composer-hint">
              Chatbot dapat membuat kesalahan. Periksa sumber pedoman yang
              disertakan.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
