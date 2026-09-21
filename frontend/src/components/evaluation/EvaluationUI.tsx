'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Check, Copy, Inbox, Terminal, X } from 'lucide-react';
import styles from './evaluation.module.css';

export function StatusBadge({
  label,
  status,
}: {
  label: string;
  status: string;
}) {
  return (
    <span className={`${styles.badge} ${styles[status] || ''}`}>{label}</span>
  );
}

export function EmptyState({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className={styles.empty}>
      <Inbox aria-hidden="true" />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

export function WorkerCommand({
  command,
  title = 'Jalankan worker di terminal backend',
  description = 'Gunakan virtual environment backend. Batch mulai dianalisis setelah worker dijalankan.',
}: {
  command: string;
  title?: string;
  description?: string;
}) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(timer);
  }, [copied]);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setError(false);
    } catch {
      setError(true);
    }
  };
  return (
    <div className={styles.commandBox}>
      <h3>
        <Terminal size={16} aria-hidden="true" />
        {title}
      </h3>
      <div className={styles.commandRow}>
        <code>{command}</code>
        <button
          className={styles.secondaryButton}
          onClick={() => void copy()}
          aria-label="Salin perintah worker"
        >
          {copied ? <Check size={16} /> : <Copy size={16} />}
          {copied ? 'Tersalin' : 'Salin'}
        </button>
      </div>
      <p aria-live="polite">
        {error
          ? 'Tidak bisa menyalin otomatis. Pilih dan salin teks perintah di atas.'
          : description}
      </p>
    </div>
  );
}

export function EvaluationDialog({
  title,
  children,
  onClose,
  busy = false,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
  wide?: boolean;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={dialogRef}
      className={`${styles.dialog} ${wide ? styles.wideDialog : ''}`}
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      onClick={(event) => {
        if (busy || event.target !== event.currentTarget) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        if (
          event.clientX < bounds.left ||
          event.clientX > bounds.right ||
          event.clientY < bounds.top ||
          event.clientY > bounds.bottom
        )
          onClose();
      }}
    >
      <header className={styles.dialogHeader}>
        <h2>{title}</h2>
        <button
          className={styles.iconButton}
          aria-label="Tutup dialog"
          disabled={busy}
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </header>
      <div className={styles.dialogBody}>{children}</div>
    </dialog>
  );
}
