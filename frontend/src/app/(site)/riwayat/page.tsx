'use client';

import { useEffect, useState } from 'react';
import { fetchSessions, fetchSessionDetails } from '../../../lib/api';
import { useAppStore } from '../../../lib/store';
import { useRouter } from 'next/navigation';

// Define proper types
interface SessionData {
  session_id: string;
  title: string;
  last_access: string;
  [key: string]: unknown;
}

interface GroupedSessions {
  [key: string]: SessionData[];
}

export default function RiwayatPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const { setSessionId, setMessages } = useAppStore();

  // Use useEffect for side effects only, inline the async operation
  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await fetchSessions();
        setSessions(data.sessions || []);
      } catch (error) {
        console.error('Error loading sessions:', error);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchData();
  }, []);

  // Keep loadSessions for potential reuse (like refresh button)
  const loadSessions = async () => {
    try {
      const data = await fetchSessions();
      setSessions(data.sessions || []);
    } catch (error) {
      console.error('Error loading sessions:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const openSession = async (id: string) => {
    try {
      const details = await fetchSessionDetails(id);
      if (details.messages) {
        setSessionId(id);
        setMessages(details.messages);
        router.push('/chat');
      }
    } catch (error) {
      console.error('Error opening session:', error);
      alert('Gagal memuat sesi ini');
    }
  };

  // Group logic
  const groupSessions = (): GroupedSessions => {
    const today = new Date();
    const groups: GroupedSessions = {
      'Hari Ini': [],
      'Kemarin': [],
      'Lebih Lama': []
    };

    sessions.forEach(s => {
      const d = new Date(s.last_access);
      const diffTime = Math.abs(today.getTime() - d.getTime());
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)); 
      
      if (diffDays <= 1 && today.getDate() === d.getDate()) {
        groups['Hari Ini'].push(s);
      } else if (diffDays <= 2) {
        groups['Kemarin'].push(s);
      } else {
        groups['Lebih Lama'].push(s);
      }
    });

    return groups;
  };

  const groups = groupSessions();

  return (
    <>
      <div className="main-header">
        <h2 className="h2">Riwayat Chat</h2>
      </div>

      <section className="view active" style={{ display: 'flex' }}>
        <div className="riwayat-body">
          {isLoading ? (
            <div style={{ textAlign: 'center', marginTop: '40px' }}><div className="spinner" /> Memuat...</div>
          ) : sessions.length === 0 ? (
            <p className="body2" style={{ color: 'var(--gray-400)', textAlign: 'center', padding: '24px 0' }}>
              Tidak ada percakapan.
            </p>
          ) : (
            Object.entries(groups).map(([label, list]) => {
              if (list.length === 0) return null;
              return (
                <div key={label} className="riwayat-group">
                  <div className="riwayat-group-label">{label}</div>
                  {list.map((s, idx) => (
                    <button key={idx} className="riwayat-item" onClick={() => openSession(s.session_id)}>
                      <div className="doc-icon">
                        <svg viewBox="0 0 24 24"><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 1 1 17 .5z"/><line x1="12" y1="8.5" x2="12" y2="13.5"/><line x1="9.5" y1="11" x2="14.5" y2="11"/></svg>
                      </div>
                      <div className="riwayat-title">{s.title}</div>
                      <div className="riwayat-time">
                        {new Date(s.last_access).toLocaleDateString('id-ID')}
                      </div>
                    </button>
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
