'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getAuthToken } from '../lib/auth';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      router.replace('/chat');
    } else {
      router.replace('/login');
    }
  }, [router]);

  return (
    <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center' }}>
      <div className="spinner" style={{ width: '24px', height: '24px', borderRadius: '50%', border: '2px solid var(--gray-200)', borderTopColor: 'var(--purple-primary)', animation: 'spin 0.7s linear infinite' }} />
    </div>
  );
}
