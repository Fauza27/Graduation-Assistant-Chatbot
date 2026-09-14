'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { BrainCircuit, Check, Play, RefreshCw, X } from 'lucide-react';
import {
  getEvaluationCases,
  getEvaluationRun,
  getEvaluationRuns,
  reviewEvaluationRecommendation,
  startEvaluationRun,
} from '@/lib/evaluationApi';
import type { EvaluationCase, EvaluationRun, EvaluationRunReport } from '@/lib/evaluationTypes';
import styles from './evaluations.module.css';

const STATUS_LABEL: Record<string, string> = {
  pending: 'Menunggu worker', running: 'Sedang dianalisis', completed: 'Selesai',
  failed: 'Gagal / parsial', cancelled: 'Dibatalkan',
};
const STAGE_LABEL: Record<string, string> = {
  information_unavailable: 'Informasi tidak tersedia', extraction: 'Ekstraksi dokumen',
  chunking: 'Chunking', query_processing: 'Pemrosesan query', retrieval: 'Retrieval',
  parent_assembly: 'Penyusunan parent', reranking: 'Reranker',
  context_assembly: 'Penyusunan konteks', generation: 'Pembuatan jawaban',
  ambiguous: 'Belum pasti', unknown: 'Tidak diketahui',
};
const REVIEW_LABEL: Record<string, string> = {
  unreviewed: 'Kandidat otomatis', correct: 'Benar', incorrect: 'Salah',
  incomplete: 'Tidak lengkap', uncertain: 'Belum pasti',
};
const errorText = (error: unknown) => error instanceof Error ? error.message : 'Terjadi kesalahan.';

export default function EvaluationsPage() {
  const [cases, setCases] = useState<EvaluationCase[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [selectedCases, setSelectedCases] = useState<Set<string>>(new Set());
  const [report, setReport] = useState<EvaluationRunReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [caseResponse, runResponse] = await Promise.all([getEvaluationCases(), getEvaluationRuns()]);
      setCases(caseResponse.data);
      setRuns(runResponse.data);
    } catch (refreshError) {
      setError(errorText(refreshError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getEvaluationCases(), getEvaluationRuns()])
      .then(([caseResponse, runResponse]) => {
        if (cancelled) return;
        setCases(caseResponse.data);
        setRuns(runResponse.data);
      })
      .catch((loadError) => { if (!cancelled) setError(errorText(loadError)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const selectedCount = selectedCases.size;
  const allSelected = cases.length > 0 && selectedCount === cases.length;
  const caseById = useMemo(
    () => new Map((report?.cases || cases).map((item) => [item.case_id, item])),
    [cases, report],
  );

  const toggleAll = () => setSelectedCases(
    allSelected ? new Set() : new Set(cases.map((item) => item.case_id)),
  );

  const queueRun = async () => {
    setWorking(true); setError(null); setMessage(null);
    try {
      const response = await startEvaluationRun(selectedCount ? Array.from(selectedCases) : undefined);
      setMessage(`${response.message}. Jalankan di terminal: ${response.next_command}`);
      setSelectedCases(new Set());
      await refresh();
    } catch (runError) { setError(errorText(runError)); }
    finally { setWorking(false); }
  };

  const openRun = async (runId: string) => {
    setWorking(true); setError(null);
    try { setReport((await getEvaluationRun(runId)).data); }
    catch (runError) { setError(errorText(runError)); }
    finally { setWorking(false); }
  };

  const reviewRecommendation = async (recommendationId: string, status: 'approved' | 'rejected') => {
    if (!report) return;
    setWorking(true); setError(null);
    try {
      await reviewEvaluationRecommendation(recommendationId, status);
      setReport((await getEvaluationRun(report.run.run_id)).data);
    } catch (reviewError) { setError(errorText(reviewError)); }
    finally { setWorking(false); }
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div><h1><BrainCircuit aria-hidden="true" /> Evaluasi RAG</h1><p>Analisis kasus gagal berdasarkan dokumen PDF asli, chunk, dan trace pipeline.</p></div>
        <button className={styles.secondaryButton} onClick={() => void refresh()} disabled={loading}><RefreshCw aria-hidden="true" /> Refresh</button>
      </header>
      {error && <div className={styles.error}>{error}</div>}
      {message && <div className={styles.message}>{message}</div>}

      <section className={styles.panel}>
        <div className={styles.panelHeader}>
          <div><h2>Antrean kasus evaluasi</h2><p>{cases.length} kandidat otomatis dan kasus yang ditandai admin.</p></div>
          <button className={styles.primaryButton} onClick={() => void queueRun()} disabled={working || cases.length === 0}><Play aria-hidden="true" />{selectedCount ? `Jadwalkan ${selectedCount} kasus` : 'Jadwalkan semua'}</button>
        </div>
        <div className={styles.tableWrap}>
          <table><thead><tr><th><input type="checkbox" checked={allSelected} onChange={toggleAll} aria-label="Pilih semua kasus" /></th><th>Pertanyaan</th><th>Status</th><th>Sumber</th><th>Catatan</th></tr></thead>
            <tbody>
              {cases.map((item) => <tr key={item.case_id}>
                <td><input type="checkbox" checked={selectedCases.has(item.case_id)} onChange={() => setSelectedCases((current) => { const next = new Set(current); if (next.has(item.case_id)) next.delete(item.case_id); else next.add(item.case_id); return next; })} aria-label={`Pilih ${item.question}`} /></td>
                <td>{item.question}</td><td><span className={styles.badge}>{REVIEW_LABEL[item.review_status] || item.review_status}</span></td><td>{item.created_by?.startsWith('system:auto:') ? 'Sistem' : 'Admin'}</td><td>{item.review_notes || '—'}</td>
              </tr>)}
              {!loading && cases.length === 0 && <tr><td colSpan={5} className={styles.empty}>Belum ada kandidat evaluasi.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className={styles.panel}>
        <div className={styles.panelHeader}><div><h2>Riwayat batch</h2><p>Pilih batch untuk melihat akar masalah dan rekomendasinya.</p></div></div>
        <div className={styles.runGrid}>
          {runs.map((run) => <button key={run.run_id} className={styles.runCard} onClick={() => void openRun(run.run_id)}>
            <span className={`${styles.runStatus} ${styles[run.status] || ''}`}>{STATUS_LABEL[run.status] || run.status}</span><strong>{run.processed_cases}/{run.total_cases} kasus</strong><small>{new Date(run.created_at).toLocaleString('id-ID')}</small>{run.error_message && <small>{run.error_message}</small>}
          </button>)}
          {!loading && runs.length === 0 && <p className={styles.empty}>Belum ada batch evaluasi.</p>}
        </div>
      </section>

      {report && <section className={styles.panel}>
        <div className={styles.panelHeader}><div><h2>Hasil batch</h2><p className={styles.mono}>{report.run.run_id}</p></div></div>
        <div className={styles.findings}>{report.findings.map((finding) => {
          const evaluationCase = caseById.get(finding.case_id);
          const evidence = report.evidence.find((item) => item.case_id === finding.case_id);
          const recommendations = report.recommendations.filter((item) => item.finding_id === finding.finding_id);
          return <article key={finding.finding_id} className={styles.finding}>
            <div className={styles.findingHeader}><div><span className={styles.stage}>{STAGE_LABEL[finding.failed_stage] || finding.failed_stage}</span><h3>{evaluationCase?.question || finding.case_id}</h3></div><strong>{Math.round(Number(finding.confidence) * 100)}%</strong></div>
            <p>{finding.root_cause}</p><p><b>Jawaban ada di dokumen asli:</b> {finding.answer_available ? 'Ya' : 'Tidak ditemukan'}</p>
            {evidence && <blockquote><b>Bukti halaman {evidence.page_start}{evidence.page_end !== evidence.page_start ? `–${evidence.page_end}` : ''}:</b> {evidence.evidence_text}</blockquote>}
            {finding.affected_chunk_ids.length > 0 && <p className={styles.mono}>Chunk terkait: {finding.affected_chunk_ids.join(', ')}</p>}
            {recommendations.map((recommendation) => <div key={recommendation.recommendation_id} className={styles.recommendation}>
              <div><span className={styles.badge}>{recommendation.target} · risiko {recommendation.risk}</span><h4>{recommendation.action}</h4><p>{recommendation.rationale}</p><small>Validasi: {recommendation.validation_plan}</small></div>
              <div className={styles.actions}><span>{recommendation.status}</span>{recommendation.status === 'proposed' && <><button aria-label="Setujui rekomendasi" onClick={() => void reviewRecommendation(recommendation.recommendation_id, 'approved')} disabled={working}><Check /></button><button aria-label="Tolak rekomendasi" onClick={() => void reviewRecommendation(recommendation.recommendation_id, 'rejected')} disabled={working}><X /></button></>}</div>
            </div>)}
          </article>;
        })}</div>
      </section>}
    </div>
  );
}
