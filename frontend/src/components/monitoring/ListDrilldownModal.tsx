'use client';

import { useMemo, useState } from 'react';
import { X, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import type { QueryLogRow, StageKey } from '@/lib/monitoringTypes';
import { STAGE_LABELS } from '@/lib/monitoringTypes';
import {
  deriveDisplayStatus, STATUS_BADGE_CLASS, STATUS_LABEL,
  formatChannel, formatDomain, fmtDateTime, fmtMs, shortId,
} from '@/lib/monitoringUtils';

const PAGE_SIZE = 15;

export interface ListDrilldownModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  rows: QueryLogRow[];
  /** Kalau diisi: tabel menampilkan kolom durasi tahap ini, dan default terurut
   * dari yang terlama (G1 — klik tahap pipeline). */
  highlightStage?: StageKey;
  onOpenDetail: (requestId: string) => void;
}

export default function ListDrilldownModal({
  open, onClose, title, subtitle, rows, highlightStage, onOpenDetail,
}: ListDrilldownModalProps) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    const s = search.trim().toLowerCase();
    let list = rows;
    if (s) {
      list = list.filter(
        (r) =>
          (r.question || '').toLowerCase().includes(s) ||
          (r.username || '').toLowerCase().includes(s) ||
          (r.session_id || '').toLowerCase().includes(s)
      );
    }
    const sorted = [...list].sort((a, b) => {
      if (highlightStage) {
        return (b[highlightStage] ?? -1) - (a[highlightStage] ?? -1);
      }
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
    return sorted;
  }, [rows, search, highlightStage]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageRows = filtered.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  if (!open) return null;

  return (
    <div className="modal-overlay show" onClick={onClose}>
      <div className="modal-card modal-card-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3>{title}</h3>
            {subtitle && <p className="modal-subtitle">{subtitle}</p>}
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Tutup">
            <X style={{ width: 18, height: 18 }} />
          </button>
        </div>

        <div className="modal-toolbar">
          <div className="search-input-wrap">
            <Search style={{ width: 15, height: 15 }} />
            <input
              placeholder="Cari pertanyaan, session, atau user…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
            />
          </div>
          <span className="modal-count">{filtered.length} hasil</span>
        </div>

        <div className="atable-scroll">
          <table className="atable">
            <thead>
              <tr>
                <th>Waktu</th>
                <th>Session / User</th>
                <th>Pertanyaan</th>
                <th>Channel</th>
                <th>Domain</th>
                {highlightStage && <th>{STAGE_LABELS[highlightStage]}</th>}
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {pageRows.length === 0 && (
                <tr>
                  <td colSpan={highlightStage ? 7 : 6} className="atable-empty">
                    Tidak ada data yang cocok.
                  </td>
                </tr>
              )}
              {pageRows.map((r) => {
                const dstatus = deriveDisplayStatus(r);
                return (
                  <tr key={r.request_id} className="atable-row-clickable" onClick={() => onOpenDetail(r.request_id)}>
                    <td className="atable-mono">{fmtDateTime(r.created_at)}</td>
                    <td>
                      <div className="atable-user">{r.username || shortId(r.session_id)}</div>
                      <div className="atable-sub">{shortId(r.session_id)}</div>
                    </td>
                    <td className="atable-question" title={r.question || ''}>
                      {r.question || '—'}
                    </td>
                    <td>{formatChannel(r.channel)}</td>
                    <td>{formatDomain(r.domain_detected)}</td>
                    {highlightStage && <td className="atable-mono">{fmtMs(r[highlightStage])}</td>}
                    <td>
                      <span className={`status-badge ${STATUS_BADGE_CLASS[dstatus]}`}>{STATUS_LABEL[dstatus]}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="modal-pagination">
            <button disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
              <ChevronLeft style={{ width: 15, height: 15 }} />
            </button>
            <span>
              Halaman {page + 1} / {totalPages}
            </span>
            <button disabled={page >= totalPages - 1} onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}>
              <ChevronRight style={{ width: 15, height: 15 }} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
