'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Bell, Search, Menu } from 'lucide-react';
import { useAdminStore } from '@/lib/adminStore';
import StatGrid from '@/components/admin/StatGrid';
import KnowledgeTreeColumn from '@/components/admin/KnowledgeTreeColumn';
import ChildChunkColumn from '@/components/admin/ChildChunkColumn';
import RelationDiagram from '@/components/admin/RelationDiagram';
import ChunkDetailPanel from '@/components/admin/ChunkDetailPanel';

export default function AdminDashboardPage() {
  const router = useRouter();
  const { tree, selectedChildId, selectedParentKey } = useAdminStore();
  const [searchDoc, setSearchDoc] = useState('');
  const [searchChild, setSearchChild] = useState('');
  const [showNotif, setShowNotif] = useState(false);

  // find the active parent based on selectedParentKey
  const getSelectedParent = () => {
    if (!tree || !selectedParentKey) return null;
    for (const doc of tree.documents) {
      for (const chap of doc.chapters) {
        for (const par of chap.parents) {
          if (`${doc.domain}-${doc.source}-${chap.section}-${par.parent_id}` === selectedParentKey) {
            return par;
          }
        }
      }
    }
    return null;
  };

  const selectedParent = getSelectedParent();

  return (
    <div className="view active">
      <header className="main-header">
        <button 
          className="icon-btn mobile-only" 
          aria-label="Buka menu" 
          type="button"
          onClick={() => {
            const sidebar = document.querySelector('.sidebar');
            const overlay = document.querySelector('.sidebar-overlay');
            if (sidebar) sidebar.classList.add('show');
            if (overlay) overlay.classList.add('show');
          }}
        >
          <Menu className="icon" />
        </button>
        <div className="main-header-titles">
          <h2>Kelola Knowledge Base</h2>
          <p className="desktop-tablet-only">Kelola dokumen sumber, parent chunk, dan child chunk yang digunakan oleh chatbot.</p>
        </div>
        <div className="notif-wrap">
          <button 
            className="icon-btn" 
            aria-label="Notifikasi" 
            type="button"
            onClick={() => setShowNotif(!showNotif)}
          >
            <Bell className="icon" />
            <span className="notif-dot"></span>
          </button>
          <div className={`notif-dropdown ${showNotif ? 'show' : ''}`}>
            <div className="notif-dropdown-head">Notifikasi</div>
            <div className="empty-state" style={{ padding: '22px 16px 26px' }}>
              <div className="empty-icon">
                <Bell style={{ width: '22px', height: '22px', stroke: 'currentColor', fill: 'none' }} />
              </div>
              <h3>Belum ada notifikasi</h3>
              <p>Pemberitahuan sistem akan muncul di sini.</p>
            </div>
          </div>
        </div>
      </header>

      <div className="content-scroll">
        <StatGrid summary={tree?.summary} />

        <div className="kb-browser">
          <div className="kb-columns">
            <div className="kb-col">
              <div className="kb-col-head">
                <div className="kb-col-head-top">
                  <span className="step-chip">1</span>
                  <h3>Struktur Dokumen</h3>
                </div>
                <p className="kb-col-hint">Pilih dokumen, lalu parent chunk di dalamnya.</p>
                <div className="input-search">
                  <Search className="icon-sm" />
                  <input 
                    className="input" 
                    placeholder="Cari dokumen, bab, atau parent…" 
                    autoComplete="off"
                    value={searchDoc}
                    onChange={(e) => setSearchDoc(e.target.value)}
                  />
                </div>
              </div>
              <div className="kb-col-body">
                <KnowledgeTreeColumn tree={tree} query={searchDoc} />
              </div>
            </div>

            <div className="kb-col">
              <div className="kb-col-head">
                <div className="kb-col-head-top">
                  <span className="step-chip">2</span>
                  <h3>Child Chunk</h3>
                </div>
                <p className="kb-col-hint">Isi dari parent chunk yang sedang dipilih.</p>
                <div className="input-search">
                  <Search className="icon-sm" />
                  <input 
                    className="input" 
                    placeholder="Cari child chunk…" 
                    autoComplete="off"
                    value={searchChild}
                    onChange={(e) => setSearchChild(e.target.value)}
                  />
                </div>
              </div>
              <div className="kb-col-body">
                <ChildChunkColumn 
                  parent={selectedParent} 
                  query={searchChild}
                  onOpenEditor={(id) => router.push(`/admin/dashboard/chunks/${id}`)}
                />
              </div>
              
              <RelationDiagram parent={selectedParent} />
            </div>
          </div>

          <ChunkDetailPanel childId={selectedChildId} />
        </div>
      </div>
    </div>
  );
}
