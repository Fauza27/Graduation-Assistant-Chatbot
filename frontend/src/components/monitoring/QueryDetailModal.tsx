'use client';

import { useEffect, useState } from 'react';
import { X, User, Clock, Layers, Coins, FileSearch, ClipboardCheck } from 'lucide-react';
import { getRequestDetail } from '@/lib/monitoringApi';
import { createEvaluationCase, getEvaluationCaseByRequest } from '@/lib/evaluationApi';
import type { ReviewStatus } from '@/lib/evaluationTypes';
import type { RequestDetail } from '@/lib/monitoringTypes';
import { PIPELINE_STAGE_KEYS, STAGE_LABELS } from '@/lib/monitoringTypes';
import {
  deriveDisplayStatus, deriveErrorDetail, formatErrorSource, STATUS_BADGE_CLASS, STATUS_LABEL,
  formatChannel, formatDomain, fmtDateTime, fmtMs, fmtUsd, fmtThousand,
} from '@/lib/monitoringUtils';
import HBarList from './charts/HBarList';

export default function QueryDetailModal({ requestId, onClose }: { requestId: string | null; onClose: () => void }) {
  const [result, setResult] = useState<{ id: string; data: RequestDetail | null; error: string | null } | null>(null);
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus>('incorrect');
  const [expectedAnswer, setExpectedAnswer] = useState('');
  const [expectedEvidence, setExpectedEvidence] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewState, setReviewState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [reviewError, setReviewError] = useState<string | null>(null);

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
    getEvaluationCaseByRequest(requestId)
      .then((response) => {
        if (cancelled || !response.data) return;
        setReviewStatus(response.data.review_status);
        setExpectedAnswer(response.data.expected_answer || '');
        setExpectedEvidence(String(response.data.expected_evidence?.notes || ''));
        setReviewNotes(response.data.review_notes || '');
        setReviewState('saved');
      })
      .catch(() => { /* Penilaian belum ada atau fitur belum diaktifkan. */ });
    return () => {
      cancelled = true;
    };
  }, [requestId]);

  const saveReview = async () => {
    if (!requestId) return;
    setReviewState('saving');
    setReviewError(null);
    try {
      await createEvaluationCase({
        request_id: requestId,
        review_status: reviewStatus,
        expected_answer: expectedAnswer.trim() || undefined,
        expected_evidence: expectedEvidence.trim() ? { notes: expectedEvidence.trim() } : undefined,
        review_notes: reviewNotes.trim() || undefined,
      });
      setReviewState('saved');
    } catch (saveError) {
      setReviewState('idle');
      setReviewError(saveError instanceof Error ? saveError.message : 'Gagal menyimpan penilaian.');
    }
  };

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

              <div className="detail-section">
                <h4><ClipboardCheck style={{ width: 14, height: 14 }} /> Penilaian untuk Evaluasi RAG</h4>
                <p style={{ margin: '0 0 12px', color: '#6b6572', fontSize: 13 }}>
                  Tandai kualitas jawaban ini. Jawaban harapan bersifat opsional dan membantu evaluator saat memeriksa dokumen asli.
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
                  {([
                    ['correct', 'Benar'], ['incorrect', 'Salah'], ['incomplete', 'Tidak lengkap'], ['uncertain', 'Belum pasti'],
                  ] as const).map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      className={`status-badge ${reviewStatus === value ? 'status-success' : 'status-neutral'}`}
                      style={{ border: '1px solid #ded6e5', cursor: 'pointer', padding: '7px 10px' }}
                      onClick={() => { setReviewStatus(value); setReviewState('idle'); }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <textarea
                  value={expectedAnswer}
                  onChange={(event) => { setExpectedAnswer(event.target.value); setReviewState('idle'); }}
                  placeholder="Jawaban yang diharapkan (opsional)"
                  rows={3}
                  style={{ width: '100%', resize: 'vertical', padding: 10, border: '1px solid #ded6e5', borderRadius: 8, marginBottom: 8 }}
                />
                <textarea
                  value={expectedEvidence}
                  onChange={(event) => { setExpectedEvidence(event.target.value); setReviewState('idle'); }}
                  placeholder="Bukti yang diharapkan, misalnya nama dokumen dan halaman (opsional)"
                  rows={2}
                  style={{ width: '100%', resize: 'vertical', padding: 10, border: '1px solid #ded6e5', borderRadius: 8, marginBottom: 8 }}
                />
                <textarea
                  value={reviewNotes}
                  onChange={(event) => { setReviewNotes(event.target.value); setReviewState('idle'); }}
                  placeholder="Catatan admin, misalnya bagian jawaban yang salah (opsional)"
                  rows={2}
                  style={{ width: '100%', resize: 'vertical', padding: 10, border: '1px solid #ded6e5', borderRadius: 8, marginBottom: 8 }}
                />
                {reviewError && <div className="modal-error" style={{ marginBottom: 8 }}>{reviewError}</div>}
                <button
                  type="button"
                  className="mon-refresh-btn"
                  onClick={() => void saveReview()}
                  disabled={reviewState === 'saving'}
                >
                  {reviewState === 'saving' ? 'Menyimpan…' : reviewState === 'saved' ? 'Penilaian tersimpan' : 'Simpan penilaian'}
                </button>
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
