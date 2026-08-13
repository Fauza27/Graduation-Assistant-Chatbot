'use client';

import { useEffect, useState } from 'react';
import { fetchProfile } from '../../../lib/api';
import { logout } from '../../../lib/auth';
import { useRouter } from 'next/navigation';
import Image from 'next/image';

export default function ProfilPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<{ nama: string; email: string; avatar_url: string | null } | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Move function declaration before useEffect
  const loadProfile = async () => {
    try {
      const data = await fetchProfile();
      setProfile({
        nama: data.nama || 'Mahasiswa STMIK WCD',
        email: data.email || 'mahasiswa@stmikwcd.ac.id',
        avatar_url: data.avatar_url || null,
      });
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, []);

  return (
    <>
      <div className="main-header">
        <h2 className="h2">Profil</h2>
      </div>

      <section className="view active" style={{ display: 'flex' }}>
        <div className="profil-body">
          {isLoading ? (
            <div className="spinner" />
          ) : (
            <>
              <div className="profil-avatar">
                {profile?.avatar_url ? (
                  <Image 
                    src={profile.avatar_url} 
                    alt="Avatar" 
                    width={68}
                    height={68}
                    style={{ borderRadius: '50%' }}
                    unoptimized
                  />
                ) : (
                  <svg viewBox="0 0 24 24" style={{ width: 34, height: 34 }}><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                )}
              </div>
              <div style={{ textAlign: 'center' }}>
                <div className="profil-name">{profile?.nama}</div>
                <div className="profil-meta">{profile?.email}</div>
              </div>
              <div className="profil-card">
                <button className="nav-item" onClick={() => router.push('/riwayat')}>
                  <svg className="icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 14"/></svg>
                  Riwayat Chat Saya
                </button>
                <button className="nav-item">
                  <svg className="icon" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
                  Dokumen Panduan (Segera Hadir)
                </button>
                <button className="nav-item logout-item" onClick={() => logout()}>
                  <svg className="icon" viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
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
