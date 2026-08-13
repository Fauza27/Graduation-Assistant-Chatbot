'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Maximize2, Loader2, X } from 'lucide-react';
import { ChunkDetail } from '@/lib/adminTypes';
import { getChunkDetail } from '@/lib/adminApi';
import ChunkEditForm from './ChunkEditForm';
import { useAdminStore } from '@/lib/adminStore';

interface ChunkDetailPanelProps {
  childId: string | null;
  isMobileShell?: boolean;
}

export default function ChunkDetailPanel({ childId, isMobileShell = false }: ChunkDetailPanelProps) {
  const router = useRouter();
  const { selectChild } = useAdminStore();
  const [detail, setDetail] = useState<ChunkDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!childId) {
      return;
    }

    let isMounted = true;
    const fetchDetail = async () => {
      setIsLoading(true);
      setDetail(null);
      try {
        const data = await getChunkDetail(childId);
        if (isMounted) {
          setDetail(data);
        }
      } catch (err) {
        // Handled silently or showing empty
        console.error('Failed to fetch detail', err);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    fetchDetail();

    return () => {
      isMounted = false;
    };
  }, [childId]);

  // Reset detail when childId becomes null (derived state pattern)
  const currentDetail = childId ? detail : null;

  const renderBody = () => {
    if (!childId) {
      return (
        <div className="empty-state">
          <div className="empty-icon">
            <svg viewBox="0 0 24 24" style={{width:'24px', height:'24px', fill:'none', stroke:'currentColor', strokeWidth:'2', strokeLinecap:'round', strokeLinejoin:'round'}}>
              <rect width="18" height="18" x="3" y="3" rx="2" />
              <path d="M3 9h18" />
              <path d="M9 21V9" />
            </svg>
          </div>
          <h3>Pilih child chunk</h3>
          <p>Pilih chunk dari kolom sebelumnya untuk melihat detail.</p>
        </div>
      );
    }

    if (isLoading) {
      return (
        <div className="empty-state">
          <Loader2 className="spin" style={{ width: '32px', height: '32px', color: 'var(--purple-primary)' }} />
          <p style={{ marginTop: '12px' }}>Memuat detail chunk...</p>
        </div>
      );
    }

    if (currentDetail) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <ChunkEditForm 
            chunk={currentDetail} 
            onSaved={(updated) => setDetail(prev => prev ? { ...prev, ...updated } : prev)}
            onDeleted={() => {
              selectChild(null, null);
            }}
          />
        </div>
      );
    }

    return (
      <div className="empty-state">
        <p>Chunk tidak ditemukan atau gagal dimuat.</p>
      </div>
    );
  };

  if (isMobileShell) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {renderBody()}
      </div>
    );
  }

  return (
    <aside className="detail-panel" id="detailPanel">
      {childId && (
        <div className="detail-panel-head">
          <h3>Detail Chunk</h3>
          <div className="detail-panel-headbtns">
            <button 
              className="icon-btn icon-btn-sm" 
              title="Buka Editor Penuh"
              onClick={() => router.push(`/admin/dashboard/chunks/${childId}`)}
              type="button"
            >
              <Maximize2 className="icon-xs" />
            </button>
            <button 
              className="icon-btn icon-btn-sm" 
              title="Tutup Panel"
              onClick={() => selectChild(null, null)}
              type="button"
            >
              <X className="icon-xs" />
            </button>
          </div>
        </div>
      )}

      <div className="detail-panel-body" style={{ padding: 0 }}>
        {renderBody()}
      </div>
    </aside>
  );
}
