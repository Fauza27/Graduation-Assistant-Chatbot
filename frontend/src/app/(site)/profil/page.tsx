'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { 
  Menu, 
  User, 
  History, 
  BookOpen, 
  LogOut 
} from 'lucide-react';

import { fetchProfile, UserProfileResponse } from '../../../lib/api';
import { logout } from '../../../lib/auth';
import { useAppStore } from '../../../lib/store';

// =============================================================================
// 1. SUB-KOMPONEN TAMPILAN
// =============================================================================

/**
 * Komponen Avatar Profil Pengguna
 */
function UserAvatar({
  avatarUrl,
  hasError,
  onError,
}: {
  avatarUrl: string | null;
  hasError: boolean;
  onError: () => void;
}) {
  return (
    <div className="profil-avatar">
      {avatarUrl && !hasError ? (
        <Image
          src={avatarUrl}
          alt="Avatar Mahasiswa"
          width={68}
          height={68}
          style={{ borderRadius: '50%' }}
          unoptimized
          onError={onError}
        />
      ) : (
        <User size={34} />
      )}
    </div>
  );
}

// =============================================================================
// 2. KOMPONEN UTAMA (ProfilPage)
// =============================================================================

export default function ProfilPage() {
  const router = useRouter();

  // --- A. STATE GLOBAL (Zustand) ---
  const setDocPanelOpen = useAppStore((state) => state.setDocPanelOpen);
  const isSidebarOpen = useAppStore((state) => state.isSidebarOpen);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);

  // --- B. STATE LOKAL ---
  const [profile, setProfile] = useState<UserProfileResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [imageError, setImageError] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  // --- C. LIFECYCLE: Memuat Data Profil dari API ---
  useEffect(() => {
    let isCancelled = false;

    const fetchData = async () => {
      try {
        const data = await fetchProfile();
        if (!isCancelled) {
          setProfile({
            nama: data.nama || 'Mahasiswa STMIK WCD',
            email: data.email || 'mahasiswa@stmikwcd.ac.id',
            avatar_url: data.avatar_url || null,
          });
          setErrorMsg(null);
        }
      } catch (error) {
        console.error('Gagal memuat profil pengguna:', error);
        if (!isCancelled) {
          setErrorMsg('Gagal memuat profil pengguna.');
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchData();

    // Pembersihan jika komponen di-unmount sebelum request selesai
    return () => {
      isCancelled = true;
    };
  }, [reloadKey]);

  // Coba muat ulang profil jika terjadi error
  const handleRetry = () => {
    setIsLoading(true);
    setReloadKey((prev) => prev + 1);
  };

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
        <h2 className="h2">Profil</h2>
      </div>

      {/* 2. Isi Halaman Profil */}
      <section className="view active" style={{ display: 'flex' }}>
        <div className="profil-body">
          {/* Kondisi 1: Loading */}
          {isLoading ? (
            <div style={{ textAlign: 'center', marginTop: '40px' }}>
              <div className="spinner" />
            </div>
          ) : /* Kondisi 2: Terjadi Galat / Error */
          errorMsg ? (
            <div style={{ textAlign: 'center', padding: '32px 16px' }}>
              <p className="body1" style={{ color: 'var(--gray-700)', marginBottom: '16px' }}>
                {errorMsg}
              </p>
              <button type="button" className="btn-primary" onClick={handleRetry} style={{ margin: '0 auto' }}>
                Coba Lagi
              </button>
            </div>
          ) : (
            /* Kondisi 3: Data Profil Berhasil Dimuat */
            <>
              {/* Foto & Identitas */}
              <UserAvatar
                avatarUrl={profile?.avatar_url || null}
                hasError={imageError}
                onError={() => setImageError(true)}
              />

              <div style={{ textAlign: 'center' }}>
                <div className="profil-name">{profile?.nama}</div>
                <div className="profil-meta">{profile?.email}</div>
              </div>

              {/* Menu Tautan Profil */}
              <div className="profil-card">
                <button
                  type="button"
                  className="nav-item"
                  onClick={() => router.push('/riwayat')}
                >
                  <History className="icon" size={20} />
                  Riwayat Chat Saya
                </button>

                <button
                  type="button"
                  className="nav-item"
                  onClick={() => setDocPanelOpen(true)}
                >
                  <BookOpen className="icon" size={20} />
                  Dokumen Panduan
                </button>

                <button
                  type="button"
                  className="nav-item logout-item"
                  onClick={() => logout()}
                >
                  <LogOut className="icon" size={20} />
                  Logout
                </button>
              </div>
            </>
          )}
        </div>
      </section>
    </>
  );
}

