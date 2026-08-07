'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useGoogleLogin } from '@react-oauth/google';
import { setAuthToken } from '../../lib/auth';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

export default function LoginPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const login = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      try {
        setIsLoading(true);
        setErrorMsg('');
        
        // Google oauth returns access_token in the implicit flow
        // We will send this to our backend to verify
        const res = await fetch(`${API_BASE_URL}/api/auth/google/verify`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ access_token: tokenResponse.access_token }),
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
      } catch (err: any) {
        console.error('Login error:', err);
        setErrorMsg(err.message || 'Terjadi kesalahan saat login.');
        setIsLoading(false);
      }
    },
    onError: () => {
      setErrorMsg('Login Google dibatalkan atau gagal.');
      setIsLoading(false);
    },
  });

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

        <button 
          className="google-btn" 
          onClick={() => {
            setIsLoading(true);
            login();
          }}
          disabled={isLoading}
        >
          {isLoading ? (
            <div className="spinner" />
          ) : (
            <svg className="icon" viewBox="0 0 20 20">
              <path fill="#4285F4" d="M19.6 10.23c0-.68-.06-1.36-.18-2H10v3.79h5.4a4.6 4.6 0 0 1-2 3.02v2.5h3.23c1.9-1.75 2.97-4.33 2.97-7.31z"/>
              <path fill="#34A853" d="M10 20c2.7 0 4.96-.89 6.62-2.42l-3.23-2.5c-.9.6-2.05.96-3.39.96-2.6 0-4.8-1.76-5.59-4.12H1.06v2.59A10 10 0 0 0 10 20z"/>
              <path fill="#FBBC05" d="M4.41 11.92a5.99 5.99 0 0 1 0-3.84V5.49H1.06a10 10 0 0 0 0 9.02l3.35-2.59z"/>
              <path fill="#EA4335" d="M10 3.98c1.47 0 2.79.5 3.83 1.5l2.87-2.87A9.6 9.6 0 0 0 10 0 10 10 0 0 0 1.06 5.49l3.35 2.59C5.2 5.72 7.4 3.98 10 3.98z"/>
            </svg>
          )}
          <span>{isLoading ? 'Sedang Masuk...' : 'Masuk dengan Google'}</span>
        </button>
        <p className="caption login-footnote">Gunakan akun Google (@stmikwcd.ac.id) untuk masuk.</p>
      </div>
      <p className="caption login-copyright">© 2026 STMIK Widya Cipta Dharma</p>
    </div>
  );
}
