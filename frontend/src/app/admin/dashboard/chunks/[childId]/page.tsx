'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronLeft, Info, Menu, Loader2 } from 'lucide-react';
import { ChunkDetail } from '@/lib/adminTypes';
import { getChunkDetail } from '@/lib/adminApi';
import { useAdminStore } from '@/lib/adminStore';
import ChunkEditForm from '@/components/admin/ChunkEditForm';
import KnowledgeTreeColumn from '@/components/admin/KnowledgeTreeColumn';

import { use } from 'react';

export default function EditChunkPage({ params }: { params: Promise<{ childId: string }> }) {
  const router = useRouter();
  const { childId } = use(params);
  
  const { tree, fetchTree } = useAdminStore();
  const [detail, setDetail] = useState<ChunkDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTree, setSearchTree] = useState('');
  const [showInfoPanel, setShowInfoPanel] = useState(false);

  useEffect(() => {
    if (!tree) fetchTree();
  }, [tree, fetchTree]);

  useEffect(() => {
    let isMounted = true;
    const fetchDetail = async () => {
      setIsLoading(true);
      try {
        const data = await getChunkDetail(childId);
        if (isMounted) setDetail(data);
      } catch (err) {
        if (isMounted) setDetail(null);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };
    fetchDetail();
    return () => { isMounted = false; };
  }, [childId]);

  const handleBack = () => {
    router.push('/admin/dashboard');
  };

  if (isLoading) {
    return (
      <div className="view active" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <Loader2 className="spin" style={{ width: '40px', height: '40px', color: 'var(--purple-primary)' }} />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="view active">
        <div className="empty-state" style={{ marginTop: '100px' }}>
          <h3>Chunk Tidak Ditemukan</h3>
          <p>Chunk dengan ID {childId} tidak ada atau gagal dimuat.</p>
          <button className="btn btn-primary" onClick={handleBack} style={{ marginTop: '16px' }} type="button">
            Kembali ke Dashboard
          </button>
        </div>
      </div>
    );
  }

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
          <h2>Edit Child Chunk</h2>
        </div>
        <button 
          className="icon-btn edit-info-toggle-btn" 
          aria-label="Info chunk" 
          type="button"
          onClick={() => setShowInfoPanel(!showInfoPanel)}
        >
          <Info className="icon" />
        </button>
      </header>

      <div className="content-scroll" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="edit-breadcrumb-bar">
          <button className="edit-back" onClick={handleBack} type="button">
            <ChevronLeft className="icon-sm" />
            Kembali
          </button>
          <span id="editCrumbs" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <button className="crumb" type="button" onClick={handleBack}>{detail.domain} ({detail.source})</button>
            <ChevronLeft className="icon-sm" style={{ transform: 'rotate(180deg)', color: 'var(--gray-400)' }} />
            <button className="crumb" type="button" onClick={handleBack}>{detail.section}</button>
            <ChevronLeft className="icon-sm" style={{ transform: 'rotate(180deg)', color: 'var(--gray-400)' }} />
            <button className="crumb" type="button" onClick={handleBack}>{detail.parent.title}</button>
            <ChevronLeft className="icon-sm" style={{ transform: 'rotate(180deg)', color: 'var(--gray-400)' }} />
            <span className="crumb current">{detail.id}</span>
          </span>
        </div>

        <div className="edit-shell">
          <div className="edit-tree-col">
            <div className="kb-col-head">
              <h3>Struktur Dokumen</h3>
              <div className="input-search" style={{ marginTop: '10px' }}>
                <input 
                  className="input" 
                  placeholder="Cari dokumen…" 
                  autoComplete="off" 
                  value={searchTree}
                  onChange={e => setSearchTree(e.target.value)}
                />
              </div>
            </div>
            <div className="kb-col-body">
              <KnowledgeTreeColumn tree={tree} query={searchTree} />
            </div>
          </div>

          <div className="edit-main-col">
            <div className="edit-main-scroll">
              <div className="edit-title-row">
                <div>
                  <h2>{detail.id} — {detail.title}</h2>
                  <p className="caption">Halaman {detail.pages}</p>
                </div>
              </div>

              <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <ChunkEditForm 
                  chunk={detail}
                  onSaved={(updated) => setDetail(prev => prev ? { ...prev, ...updated } : prev)}
                  onDeleted={() => router.push('/admin/dashboard')}
                  layout="full"
                />
              </div>
            </div>
          </div>

          {/* overlay for mobile info panel */}
          {showInfoPanel && (
            <div 
              className="detail-overlay show" 
              onClick={() => setShowInfoPanel(false)}
            ></div>
          )}

          <div className={`edit-info-col ${showInfoPanel ? 'show' : ''}`}>
            <div className="edit-info-head">
              <h3>Informasi Chunk</h3>
            </div>
            <div className="edit-info-body">
              <div className="info-field">
                <span className="info-label">CHILD ID</span>
                <span className="info-value">{detail.id}</span>
              </div>
              <div className="info-field">
                <span className="info-label">PARENT CHUNK</span>
                <span className="info-value">{detail.parent.title}</span>
              </div>
              <div className="info-field">
                <span className="info-label">DOMAIN</span>
                <span className="info-value">{detail.domain}</span>
              </div>
              <div className="info-field">
                <span className="info-label">SOURCE</span>
                <span className="info-value">{detail.source}</span>
              </div>
              <div className="info-field">
                <span className="info-label">SECTION</span>
                <span className="info-value">{detail.section}</span>
              </div>
              <div className="info-field">
                <span className="info-label">PAGES</span>
                <span className="info-value">{detail.pages}</span>
              </div>
              <hr style={{ border: 0, borderTop: '1px solid var(--border)', margin: '8px 0' }} />
              <div className="info-field">
                <span className="info-label">STATUS EMBEDDING</span>
                <span className="info-value" style={{ marginTop: '4px', display: 'block' }}>
                  {detail.embedding_status === 'success' && <span className="status-badge status-success">Success</span>}
                  {detail.embedding_status === 'stale' && <span className="status-badge status-warning">Stale</span>}
                  {detail.embedding_status === 'failed' && <span className="status-badge status-danger">Failed</span>}
                  {detail.embedding_status === 'pending' && <span className="status-badge status-info">Pending</span>}
                </span>
              </div>
              <div className="info-field">
                <span className="info-value" style={{ fontSize: '11px', color: 'var(--gray-400)' }}>
                  Terakhir di-embed: {detail.reembedded_at ? new Date(detail.reembedded_at).toLocaleString('id-ID') : 'Belum pernah'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
