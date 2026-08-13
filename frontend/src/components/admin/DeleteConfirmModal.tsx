'use client';

import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { ChunkDetail } from '@/lib/adminTypes';

interface DeleteConfirmModalProps {
  chunk: ChunkDetail;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
}

export default function DeleteConfirmModal({ chunk, onConfirm, onCancel }: DeleteConfirmModalProps) {
  const [isDeleting, setIsDeleting] = useState(false);

  const handleConfirm = async () => {
    setIsDeleting(true);
    try {
      await onConfirm();
    } catch {
      // errors should be caught by caller to show toast
      setIsDeleting(false);
    }
  };

  return (
    <div className="modal-overlay show">
      <div className="modal-card">
        <div className="modal-danger-icon">
          <Trash2 size={22} />
        </div>
        <div className="modal-head">
          <h3>Hapus Child Chunk?</h3>
        </div>
        <p className="modal-sub">
          Apakah Anda yakin ingin menghapus chunk <strong>{chunk.id.substring(0, 12)}... — {chunk.title}</strong>? 
          Tindakan ini tidak dapat dibatalkan.
        </p>

        <div className="modal-actions">
          <button 
            className="btn btn-outline-gray" 
            onClick={onCancel} 
            disabled={isDeleting}
            type="button"
          >
            Batal
          </button>
          <button 
            className="btn btn-danger-solid" 
            onClick={handleConfirm} 
            disabled={isDeleting}
            type="button"
          >
            {isDeleting ? 'Menghapus...' : 'Hapus Chunk'}
          </button>
        </div>
      </div>
    </div>
  );
}
