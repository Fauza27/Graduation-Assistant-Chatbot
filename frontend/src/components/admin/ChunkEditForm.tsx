'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { RefreshCw, Trash2, Save } from 'lucide-react';
import { ChunkDetail } from '@/lib/adminTypes';
import { saveChunk, deleteChunk, ChunkSaveResponse } from '@/lib/adminApi';
import { useAdminStore } from '@/lib/adminStore';
import ReembedStatusModal from './ReembedStatusModal';
import DeleteConfirmModal from './DeleteConfirmModal';

interface ChunkEditFormProps {
  chunk: ChunkDetail;
  onSaved: (result: ChunkSaveResponse) => void;
  onDeleted?: () => void;
  layout?: 'sidebar' | 'full';
}

export default function ChunkEditForm({ chunk, onSaved, onDeleted, layout = 'sidebar' }: ChunkEditFormProps) {
  const router = useRouter();
  const { patchChunkInTree, removeChunkFromTree } = useAdminStore();
  
  const [activeTab, setActiveTab] = useState<'metadata' | 'content'>('metadata');
  
  const [titleDraft, setTitleDraft] = useState(chunk.title);
  const [pagesDraft, setPagesDraft] = useState(chunk.pages);
  const [contentDraft, setContentDraft] = useState(chunk.content);
  
  const [isSaving, setIsSaving] = useState(false);
  const [showReembedModal, setShowReembedModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  // Sync draft when chunk prop changes
  useEffect(() => {
    setTitleDraft(chunk.title);
    setPagesDraft(chunk.pages);
    setContentDraft(chunk.content);
  }, [chunk]);

  const handleSave = async () => {
    const updates: any = {};
    if (titleDraft !== chunk.title) updates.title = titleDraft;
    if (pagesDraft !== chunk.pages) updates.pages = pagesDraft;
    if (contentDraft !== chunk.content) updates.content = contentDraft;

    if (Object.keys(updates).length === 0) {
      showToast('Tidak ada perubahan.');
      return;
    }

    setIsSaving(true);
    try {
      const result = await saveChunk(chunk.id, updates);
      patchChunkInTree(chunk.id, { embedding_status: result.embedding_status });
      onSaved(result);
      showToast(result.message);
    } catch (err: any) {
      showToast(err.message || 'Gagal menyimpan.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      const result = await deleteChunk(chunk.id);
      removeChunkFromTree(chunk.id, result.parent_deleted);
      showToast(result.message);
      setShowDeleteModal(false);
      if (onDeleted) {
        onDeleted();
      }
    } catch (err: any) {
      showToast(err.message || 'Gagal menghapus chunk.');
      throw err; // rethrow to let modal know it failed
    }
  };

  // Simple global toast for the admin forms
  const showToast = (msg: string) => {
    const existing = document.getElementById('admin-toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.id = 'admin-toast';
    toast.className = 'toast';
    toast.innerHTML = `<svg class="icon-sm" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>${msg}`;
    document.body.appendChild(toast);
    
    // trigger animation
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 200);
    }, 3000);
  };

  const isSidebar = layout === 'sidebar';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className={isSidebar ? "detail-tabs" : "edit-tabs"}>
        <button 
          className={`tab-btn ${activeTab === 'metadata' ? 'active' : ''}`}
          onClick={() => setActiveTab('metadata')}
          type="button"
        >
          Metadata
        </button>
        <button 
          className={`tab-btn ${activeTab === 'content' ? 'active' : ''}`}
          onClick={() => setActiveTab('content')}
          type="button"
        >
          Content
        </button>
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, padding: isSidebar ? '16px' : '8px 0 0 0' }}>
        {activeTab === 'metadata' && (
          <div className="tabpanel active" style={{ flex: 1 }}>
            <div className="form-grid">
              <div className="field span-2">
                <label>Judul Child Chunk</label>
                <input 
                  className="input" 
                  value={titleDraft} 
                  onChange={e => setTitleDraft(e.target.value)}
                />
              </div>
              <div className="field">
                <label>Halaman (Pages)</label>
                <input 
                  className="input" 
                  value={pagesDraft}
                  onChange={e => setPagesDraft(e.target.value)}
                />
              </div>
              <div className="field">
                <label>Status Embedding</label>
                <div style={{ marginTop: '10px' }}>
                  {chunk.embedding_status === 'success' && <span className="status-badge status-success">Tersinkronisasi</span>}
                  {chunk.embedding_status === 'stale' && <span className="status-badge status-warning">Perlu Re-embed</span>}
                  {chunk.embedding_status === 'failed' && <span className="status-badge status-danger">Gagal</span>}
                  {chunk.embedding_status === 'pending' && <span className="status-badge status-info">Pending</span>}
                </div>
              </div>
              <div className="field span-2" style={{ marginTop: '6px' }}>
                <label>Info Parent Chunk (Read-only)</label>
                <div className="meta-row-2">
                  <div className="info-field">
                    <span className="info-label">Domain</span>
                    <span className="info-value">{chunk.domain}</span>
                  </div>
                  <div className="info-field">
                    <span className="info-label">Dokumen</span>
                    <span className="info-value">{chunk.source}</span>
                  </div>
                  <div className="info-field">
                    <span className="info-label">Bab</span>
                    <span className="info-value">{chunk.section}</span>
                  </div>
                  <div className="info-field">
                    <span className="info-label">Parent Title</span>
                    <span className="info-value">{chunk.parent.title}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'content' && (
          <div className="tabpanel active" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div className="field" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <label>Konten Teks</label>
              <textarea 
                className="textarea" 
                style={{ flex: 1, resize: 'none' }}
                value={contentDraft}
                onChange={e => setContentDraft(e.target.value)}
              />
            </div>
          </div>
        )}
      </div>

      <div className={isSidebar ? "detail-panel-actions" : "edit-actionbar"} style={{ marginTop: 'auto' }}>
        <button className="btn btn-outline-gray btn-sm" onClick={() => setShowReembedModal(true)} type="button">
          <RefreshCw className="icon-sm" />
          {!isSidebar && 'Re-Embed'}
        </button>
        <button className="btn btn-danger btn-sm" onClick={() => setShowDeleteModal(true)} type="button">
          <Trash2 className="icon-sm" />
          {!isSidebar && 'Delete'}
        </button>
        <button 
          className="btn btn-primary btn-sm" 
          style={!isSidebar ? { marginLeft: 'auto', flex: '0 0 auto', padding: '10px 22px' } : undefined} 
          onClick={handleSave} 
          disabled={isSaving} 
          type="button"
        >
          {isSaving ? 'Menyimpan...' : 'Simpan Perubahan'}
        </button>
      </div>

      {showReembedModal && (
        <ReembedStatusModal 
          childId={chunk.id}
          onDone={(finalStatus) => {
            patchChunkInTree(chunk.id, { embedding_status: finalStatus });
            onSaved({ ...chunk, embedding_status: finalStatus, message: '', content_changed: false });
          }}
          onClose={() => setShowReembedModal(false)}
        />
      )}

      {showDeleteModal && (
        <DeleteConfirmModal 
          chunk={chunk}
          onConfirm={handleDelete}
          onCancel={() => setShowDeleteModal(false)}
        />
      )}
    </div>
  );
}
