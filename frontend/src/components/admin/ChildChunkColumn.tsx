'use client';

import { AlignLeft, Maximize2 } from 'lucide-react';
import { ParentNode } from '@/lib/adminTypes';
import { useAdminStore } from '@/lib/adminStore';

interface ChildChunkColumnProps {
  parent: ParentNode | null;
  query: string;
  onOpenEditor: (childId: string) => void;
}

export default function ChildChunkColumn({ parent, query, onOpenEditor }: ChildChunkColumnProps) {
  const { selectedChildId, selectChild } = useAdminStore();

  if (!parent) {
    return (
      <div className="empty-state">
        <div className="empty-icon"><AlignLeft /></div>
        <h3>Pilih Parent Chunk</h3>
        <p>Silakan pilih salah satu parent chunk di kolom Struktur Dokumen.</p>
      </div>
    );
  }

  const q = query.toLowerCase();
  const filteredChildren = parent.children.filter(c => 
    c.title.toLowerCase().includes(q) || c.id.toLowerCase().includes(q)
  );

  if (filteredChildren.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon"><AlignLeft /></div>
        <h3>Tidak ada child chunk</h3>
        <p>Parent ini belum memiliki child chunk atau tidak sesuai kata kunci.</p>
      </div>
    );
  }

  return (
    <>
      {filteredChildren.map(child => {
        const isSelected = selectedChildId === child.id;
        let badgeClass = 'status-info';
        let statusText = 'Pending';
        if (child.embedding_status === 'success') { badgeClass = 'status-success'; statusText = 'Tersinkronisasi'; }
        if (child.embedding_status === 'stale') { badgeClass = 'status-warning'; statusText = 'Perlu Re-embed'; }
        if (child.embedding_status === 'failed') { badgeClass = 'status-danger'; statusText = 'Gagal'; }

        return (
          <button 
            key={child.id} 
            className={`list-item ${isSelected ? 'selected' : ''}`}
            onClick={() => selectChild(child.id, useAdminStore.getState().selectedParentKey)}
            type="button"
          >
            <div className="list-item-top">
              <span className="li-id">{child.id.substring(0, 12)}...</span>
              <div className="list-item-actions">
                <div 
                  className="icon-btn icon-btn-sm" 
                  title="Buka Editor Penuh"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenEditor(child.id);
                  }}
                >
                  <Maximize2 className="icon-xs" />
                </div>
              </div>
            </div>
            <div className="li-title">{child.title}</div>
            <div className="list-item-top" style={{ marginTop: '3px' }}>
              <div className="li-sub">Hal. {child.pages}</div>
              <div className={`status-badge ${badgeClass} li-page-badge`}>{statusText}</div>
            </div>
          </button>
        );
      })}
    </>
  );
}
