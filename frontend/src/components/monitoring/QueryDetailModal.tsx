'use client';

import { useEffect, useState } from 'react';
import { X, User, Clock, Layers, Coins, FileSearch } from 'lucide-react';
import { getRequestDetail } from '@/lib/monitoringApi';
import type { RequestDetail } from '@/lib/monitoringTypes';
import { PIPELINE_STAGE_KEYS, STAGE_LABELS } from '@/lib/monitoringTypes';
import {
  deriveDisplayStatus, deriveErrorDetail, formatErrorSource, STATUS_BADGE_CLASS, STATUS_LABEL,
  formatChannel, formatDomain, fmtDateTime, fmtMs, fmtUsd, fmtThousand,
} from '@/lib/monitoringUtils';
import HBarList from './charts/HBarList';

export default function QueryDetailModal({ requestId, onClose }: { requestId: string | null; onClose: () => void }) {
  const [result, setResult] = useState<{ id: string; data: RequestDetail | null; error: string | null } | null>(null);

  useEffect(() => {
    if (!requestId) return;
    let cancelled = false;
    getRequestDetail(requestId)
      .then((res) => {
        if (!cancelled) setResult({ id: requestId, data: res.data, error: null });
      })
      .catch((err) => {
        if (!cancelled) {
          setResult({ id: requestId, data: null, error: err instanceof Error ? err.message : 'Gagal memuat detail request.' });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [requestId]);

  if (!requestId) return null;

  const loading = result?.id !== requestId;
  const data = result?.id === requestId ? result.data : null;
  const error = result?.id === requestId ? result.error : null;
  const dstatus = data ? deriveDisplayStatus(data) : null;

  return (
    <div className="modal-overlay show" onClick={onClose}>
      <div className="modal-card modal-card-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3>Detail Request</h3>
            <p className="modal-subtitle atable-mono">{requestId}</p>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Tutup">
            <X style={{ width: 18, height: 18 }} />
          </button>
        </div>

        <div className="modal-body-scroll">
          {loading && <div className="modal-loading">Memuat detail…</div>}
          {error && <div className="modal-error">{error}</div>}

          {data && dstatus && (
            <>
              {/* Pertanyaan + identitas */}
              <div className="detail-question-block">
                <p className="detail-question-text">&ldquo;{data.question || '(tidak ada teks pertanyaan)'}&rdquo;</p>
                <span className={`status-badge ${STATUS_BADGE_CLASS[dstatus]}`}>{STATUS_LABEL[dstatus]}</span>
              </div>

              <div className="detail-info-grid">
                <div className="info-field">
                  <span className="info-label">
                    <User style={{ width: 13, height: 13 }} /> User
                  </span>
                  <span className="info-value">{data.username || '—'}</span>
                </div>
                <div className="info-field">
                  <span className="info-label">Session</span>
                  <span className="info-value atable-mono">{data.session_id || '—'}</span>
                </div>
                <div className="info-field">
                  <span className="info-label">Channel</span>
                  <span className="info-value">{formatChannel(data.channel)}</span>
                </div>
                <div className="info-field">
                  <span className="info-label">Domain</span>
                  <span className="info-value">{formatDomain(data.domain_detected)}</span>
                </div>
                <div className="info-field">
                  <span className="info-label">
                    <Clock style={{ width: 13, height: 13 }} /> Waktu
                  </span>
                  <span className="info-value">{fmtDateTime(data.created_at)}</span>
                </div>
                <div className="info-field">
                  <span className="info-label">Total Latency</span>
                  <span className="info-value">{fmtMs(data.total_ms)}</span>
                </div>
              </div>

              {/* Error detail kalau ada */}
              {data.status === 'error' && (
                <div className="detail-error-box">
                  <div className="deb-title">{formatErrorSource(data.error_source)}</div>
                  <div className="deb-detail">{deriveErrorDetail(data.error_source, data.error_type)}</div>
                  {data.openai_retry_count > 0 && (
                    <div className="deb-retry">Retry OpenAI: {data.openai_retry_count}x sebelum gagal</div>
                  )}
                </div>
              )}

              {/* G1: breakdown latency 8 tahap untuk request ini */}
              <div className="detail-section">
                <h4>
                  <Layers style={{ width: 14, height: 14 }} /> Breakdown Latency per Tahap
                </h4>
                <HBarList
                  items={PIPELINE_STAGE_KEYS.map((key) => ({
                    label: STAGE_LABELS[key],
                    value: data[key] ?? 0,
                    valueLabel: data[key] != null ? fmtMs(data[key]) : 'tidak dilalui',
                  }))}
                  numbered
                />
              </div>

              {/* D: token & cost */}
              {data.status === 'success' && (
                <div className="detail-section">
                  <h4>
                    <Coins style={{ width: 14, height: 14 }} /> Token &amp; Biaya
                  </h4>
                  <div className="detail-info-grid">
                    <div className="info-field">
                      <span className="info-label">Token Input</span>
                      <span className="info-value">{fmtThousand(data.input_tokens)}</span>
                    </div>
                    <div className="info-field">
                      <span className="info-label">Token Output</span>
                      <span className="info-value">{fmtThousand(data.output_tokens)}</span>
                    </div>
                    <div className="info-field">
                      <span className="info-label">Biaya LLM</span>
                      <span className="info-value">{fmtUsd(data.llm_cost_usd)}</span>
                    </div>
                    <div className="info-field">
                      <span className="info-label">Biaya Embedding</span>
                      <span className="info-value">{fmtUsd(data.embedding_cost_usd, 6)}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* G5: detail cross-encoder per dokumen kandidat */}
              {data.retrieval_detail && data.retrieval_detail.length > 0 && (
                <div className="detail-section">
                  <h4>
                    <FileSearch style={{ width: 14, height: 14 }} /> Detail Cross-Encoder ({data.retrieval_detail.length} kandidat)
                  </h4>
                  <div className="atable-scroll">
                    <table className="atable atable-compact">
                      <thead>
                        <tr>
                          <th>Dokumen</th>
                          <th>Skor</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...data.retrieval_detail]
                          .sort((a, b) => b.score - a.score)
                          .map((c) => (
                            <tr key={c.parent_id}>
                              <td className="atable-question" title={c.parent_id}>
                                {c.title || c.parent_id}
                              </td>
                              <td className="atable-mono">{c.score.toFixed(4)}</td>
                              <td>
                                <span className={`status-badge ${c.accepted ? 'status-success' : 'status-neutral'}`}>
                                  {c.accepted ? 'Diterima' : 'Ditolak'}
                                </span>
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              {data.is_no_relevant_doc && (
                <div className="detail-section">
                  <div className="empty-state" style={{ padding: '18px 14px' }}>
                    <p style={{ margin: 0 }}>Tidak ada dokumen relevan yang ditemukan untuk pertanyaan ini.</p>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
