'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { GoogleLogin } from '@react-oauth/google';
import { setAuthToken } from '../../lib/auth';

// Define proper types for Google OAuth response
interface GoogleCredentialResponse {
  credential: string;
  select_by?: string;
  client_id?: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

export default function LoginPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleGoogleSuccess = async (credentialResponse: GoogleCredentialResponse) => {
    try {
      setIsLoading(true);
      setErrorMsg('');
      
      const res = await fetch(`${API_BASE_URL}/api/auth/google/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id_token: credentialResponse.credential }),
      });

      if (!res.ok) {
        throw new Error('Gagal login ke server WCD');
      }

      const data = await res.json();
      if (data.access_token) {
        setAuthToken(data.access_token);
        router.replace('/chat');
      } else {
        throw new Error('Token tidak valid dari server');
      }
    } catch (err: Error | unknown) {
      console.error('Login error:', err);
      const errorMessage = err instanceof Error ? err.message : 'Terjadi kesalahan saat login.';
      setErrorMsg(errorMessage);
      setIsLoading(false);
    }
  };

  const handleGoogleError = () => {
    setErrorMsg('Login Google dibatalkan atau gagal.');
    setIsLoading(false);
  };

  return (
    <div className="login-screen">
      <div className="login-blob blob-a" />
      <div className="login-blob blob-b" />
      <div className="login-card">
        <svg className="brand-mark login-mark" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
          <circle cx="20" cy="20" r="19" fill="#F5F1FC" stroke="#6D28D9" strokeWidth="1.4" />
          <circle cx="20" cy="20" r="12.5" fill="none" stroke="#6D28D9" strokeWidth="1.4" />
          <circle cx="20" cy="20" r="4" fill="#6D28D9" />
        </svg>
        <h1 className="h2">Asisten WCD</h1>
        <p className="body2 login-sub">
          Tanya jawab seputar PI, KKP, Skripsi, dan Jalur Lulus Non Skripsi — khusus mahasiswa STMIK Widya Cipta Dharma.
        </p>
        
        {errorMsg && <p className="body2" style={{ color: 'var(--danger)', marginBottom: '10px' }}>{errorMsg}</p>}

        <div style={{ display: 'flex', justifyContent: 'center', minHeight: '40px' }}>
          {isLoading ? (
            <div className="spinner" />
          ) : (
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={handleGoogleError}
              shape="pill"
            />
          )}
        </div>
        <p className="caption login-footnote">Gunakan akun Google Anda untuk masuk.</p>
      </div>
      <p className="caption login-copyright">© 2026 STMIK Widya Cipta Dharma</p>
    </div>
  );
}
