'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft,
  Check,
  FileSearch,
  LoaderCircle,
  RefreshCw,
  X,
} from 'lucide-react';
import {
  getEvaluationRun,
  reviewEvaluationRecommendation,
} from '@/lib/evaluationApi';
import type { EvaluationRunReport } from '@/lib/evaluationTypes';
import {
  errorMessage,
  formatRunDate,
  isActiveRun,
  recommendationSummary,
  RECOMMENDATION_LABELS,
  RUN_LABELS,
  STAGE_LABELS,
  workerCommand,
} from '@/lib/evaluationUtils';
import {
  EmptyState,
  StatusBadge,
  WorkerCommand,
} from '@/components/evaluation/EvaluationUI';
import styles from '@/components/evaluation/evaluation.module.css';

export default function EvaluationRunPage() {
  const { runId } = useParams<{ runId: string }>();
  const [report, setReport] = useState<EvaluationRunReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [stage, setStage] = useState('all');
  const requestRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    try {
      const response = await getEvaluationRun(runId, controller.signal);
      if (!controller.signal.aborted) {
        setReport(response.data);
        setError(null);
      }
    } catch (loadError) {
      if (!controller.signal.aborted) setError(errorMessage(loadError));
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    const controller = new AbortController();
    requestRef.current = controller;
    getEvaluationRun(runId, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) setReport(response.data);
      })
      .catch((loadError) => {
        if (!controller.signal.aborted) setError(errorMessage(loadError));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [runId]);

  const active = report ? isActiveRun(report.run) : false;
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') void load();
    }, 15000);
    return () => clearInterval(timer);
  }, [active, load]);

  const grouped = useMemo(() => {
    const cases = new Map(report?.cases.map((item) => [item.case_id, item]));
    const recommendations = new Map<
      string,
      EvaluationRunReport['recommendations']
    >();
    const evidence = new Map<string, EvaluationRunReport['evidence']>();
    for (const item of report?.recommendations || []) {
      const list = recommendations.get(item.finding_id) || [];
      list.push(item);
      recommendations.set(item.finding_id, list);
    }
    for (const item of report?.evidence || []) {
      const list = evidence.get(item.case_id) || [];
      list.push(item);
      evidence.set(item.case_id, list);
    }
    return { cases, recommendations, evidence };
  }, [report]);

  const review = async (id: string, status: 'approved' | 'rejected') => {
    if (busy) return;
    setBusy(id);
    setError(null);
    try {
      const response = await reviewEvaluationRecommendation(id, status);
      setReport((current) =>
        current
          ? {
              ...current,
              recommendations: current.recommendations.map((item) =>
                item.recommendation_id === id ? response.data : item,
              ),
            }
          : current,
      );
    } catch (reviewError) {
      setError(errorMessage(reviewError));
    } finally {
      setBusy(null);
    }
  };

  const findings =
    report?.findings.filter(
      (item) => stage === 'all' || item.failed_stage === stage,
    ) || [];
  const stages = [
    ...new Set(report?.findings.map((item) => item.failed_stage)),
  ];
  const findingCases = new Set(report?.findings.map((item) => item.case_id));
  const unfinished =
    report?.case_statuses.filter((item) => !findingCases.has(item.case_id)) ||
    [];
  const progress = report?.run.total_cases
    ? Math.min(
        100,
        Math.round((report.run.processed_cases / report.run.total_cases) * 100),
      )
    : 0;

  return (
    <div className={styles.page}>
      <div className={styles.pageInner}>
        <Link className={styles.textLink} href="/admin/dashboard/evaluations">
          <ArrowLeft size={16} />
          Kembali ke evaluasi
        </Link>
        <header className={styles.header}>
          <div>
            <h1>
              <FileSearch size={25} />
              Hasil evaluasi
            </h1>
            <p>Penyebab gagal dan rekomendasi berdasarkan bukti pipeline.</p>
          </div>
          <button
            className={styles.secondaryButton}
            disabled={loading || Boolean(busy)}
            onClick={() => {
              setLoading(true);
              void load();
            }}
          >
            <RefreshCw
              size={16}
              className={loading ? styles.spin : undefined}
            />
            Perbarui
          </button>
        </header>
        {error && (
          <p className={styles.error} role="alert">
            {error}{' '}
            <button
              className={styles.textButton}
              onClick={() => {
                setLoading(true);
                void load();
              }}
            >
              Coba kembali
            </button>
          </p>
        )}
        {loading && !report && (
          <p className={styles.loading} role="status">
            <LoaderCircle className={styles.spin} size={18} />
            Memuat batch…
          </p>
        )}
        {!loading && !report && (
          <EmptyState title="Batch belum dapat ditampilkan">
            Periksa koneksi dan ID batch, lalu coba kembali.
          </EmptyState>
        )}
        {report && (
          <>
            <section className={styles.panel}>
              <div className={styles.batchSummary}>
                <div className={styles.sectionHeader} style={{ padding: 0 }}>
                  <div>
                    <StatusBadge
                      status={report.run.status}
                      label={RUN_LABELS[report.run.status]}
                    />
                    <p>
                      {formatRunDate(report.run.created_at)} ·{' '}
                      {report.run.evaluator_model}
                    </p>
                  </div>
                  <strong>
                    {report.run.processed_cases} / {report.run.total_cases}{' '}
                    kasus diproses
                  </strong>
                </div>
                <div
                  className={styles.progress}
                  role="progressbar"
                  aria-label="Progres evaluasi batch"
                  aria-valuenow={progress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <span style={{ width: `${progress}%` }} />
                </div>
                <p className={styles.mono}>ID batch: {report.run.run_id}</p>
                {report.run.error_message && (
                  <p className={styles.error}>{report.run.error_message}</p>
                )}
                {report.run.status === 'pending' && (
                  <>
                    <p>
                      Batch sudah diantrekan. Analisis belum dimulai dan
                      memerlukan worker manual.
                    </p>
                    <div style={{ marginTop: 14 }}>
                      <WorkerCommand
                        command={workerCommand(report.run.run_id)}
                      />
                    </div>
                  </>
                )}
                {report.run.status === 'running' && (
                  <p role="status">
                    Worker sedang membaca dokumen dan memeriksa kasus. Hasil
                    diperbarui otomatis setiap 15 detik selama halaman aktif.
                  </p>
                )}
              </div>
            </section>
            <div className={styles.toolbar} style={{ padding: 0 }}>
              <h2 style={{ fontSize: 16 }}>
                Temuan ({report.findings.length})
              </h2>
              <select
                className={styles.select}
                aria-label="Filter tahap kegagalan"
                value={stage}
                onChange={(event) => setStage(event.target.value)}
              >
                <option value="all">Semua tahap kegagalan</option>
                {stages.map((value) => (
                  <option key={value} value={value}>
                    {STAGE_LABELS[value] || value}
                  </option>
                ))}
              </select>
            </div>
            <div className={styles.findings}>
              {findings.map((finding) => {
                const item = grouped.cases.get(finding.case_id);
                const recommendations =
                  grouped.recommendations.get(finding.finding_id) || [];
                const evidence = grouped.evidence.get(finding.case_id) || [];
                return (
                  <article key={finding.finding_id} className={styles.finding}>
                    <StatusBadge
                      status="uncertain"
                      label={
                        STAGE_LABELS[finding.failed_stage] ||
                        finding.failed_stage
                      }
                    />
                    <h3>{item?.question || 'Pertanyaan tidak tersedia'}</h3>
                    <p className={styles.reason}>
                      <strong>Alasan gagal</strong>
                      {finding.root_cause}
                    </p>
                    {recommendations.map((recommendation) => (
                      <div
                        className={styles.recommendation}
                        key={recommendation.recommendation_id}
                      >
                        <h4>Rekomendasi perbaikan</h4>
                        <code className={styles.target}>
                          {recommendation.target}
                        </code>
                        <p>{recommendationSummary(recommendation.action)}</p>
                        <div className={styles.recommendationActions}>
                          <StatusBadge
                            status={recommendation.status}
                            label={
                              RECOMMENDATION_LABELS[recommendation.status] ||
                              recommendation.status
                            }
                          />
                          {recommendation.status === 'proposed' && (
                            <>
                              <button
                                className={styles.secondaryButton}
                                disabled={Boolean(busy)}
                                onClick={() =>
                                  void review(
                                    recommendation.recommendation_id,
                                    'rejected',
                                  )
                                }
                              >
                                <X size={15} />
                                Tolak
                              </button>
                              <button
                                className={styles.primaryButton}
                                disabled={Boolean(busy)}
                                onClick={() =>
                                  void review(
                                    recommendation.recommendation_id,
                                    'approved',
                                  )
                                }
                              >
                                {busy === recommendation.recommendation_id ? (
                                  <LoaderCircle
                                    className={styles.spin}
                                    size={15}
                                  />
                                ) : (
                                  <Check size={15} />
                                )}
                                Setujui
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    ))}
                    {!recommendations.length && (
                      <p className={styles.hint} style={{ marginTop: 12 }}>
                        Belum ada rekomendasi untuk temuan ini.
                      </p>
                    )}
                    {(evidence.length > 0 ||
                      item?.actual_answer ||
                      item?.expected_answer) && (
                      <details
                        className={styles.disclosure}
                        style={{ marginTop: 15 }}
                      >
                        <summary>Lihat jawaban dan bukti pendukung</summary>
                        {item?.actual_answer && (
                          <div>
                            <h4>Jawaban chatbot saat kasus dibuat</h4>
                            <p className={styles.answerText}>
                              {item.actual_answer}
                            </p>
                          </div>
                        )}
                        {item?.expected_answer && (
                          <div>
                            <h4>Jawaban yang diharapkan admin</h4>
                            <p className={styles.answerText}>
                              {item.expected_answer}
                            </p>
                          </div>
                        )}
                        {evidence.map((proof) => (
                          <blockquote
                            className={styles.evidence}
                            key={proof.evidence_id}
                          >
                            <small>
                              Halaman PDF {proof.page_start ?? '—'}
                              {proof.page_end &&
                              proof.page_end !== proof.page_start
                                ? `–${proof.page_end}`
                                : ''}{' '}
                              ·{' '}
                              {proof.is_verified
                                ? 'Bukti terverifikasi'
                                : 'Belum terverifikasi'}
                            </small>
                            <p>{proof.evidence_text}</p>
                          </blockquote>
                        ))}
                      </details>
                    )}
                  </article>
                );
              })}
            </div>
            {!findings.length && (
              <section className={styles.panel}>
                <EmptyState
                  title={
                    active
                      ? 'Temuan belum tersedia'
                      : 'Tidak ada temuan pada tampilan ini'
                  }
                >
                  {active
                    ? 'Hasil akan muncul setelah worker selesai memeriksa kasus. Anda boleh meninggalkan halaman ini.'
                    : 'Coba filter tahap lain atau periksa status pemrosesan kasus di bawah.'}
                </EmptyState>
              </section>
            )}
            {unfinished.length > 0 && (
              <section className={styles.panel}>
                <div className={styles.sectionHeader}>
                  <div>
                    <h2>Status kasus lainnya</h2>
                    <p>
                      Kasus berikut belum memiliki temuan yang dapat
                      ditampilkan.
                    </p>
                  </div>
                </div>
                <div className={styles.runList}>
                  {unfinished.map((item) => (
                    <div className={styles.runCard} key={item.case_id}>
                      <div>
                        <strong>
                          {grouped.cases.get(item.case_id)?.question ||
                            item.case_id}
                        </strong>
                        <p className={styles.sourceText}>
                          {item.error_message ||
                            {
                              pending: 'Menunggu pemeriksaan',
                              running: 'Sedang diperiksa',
                              completed: 'Pemeriksaan selesai',
                              failed: 'Pemeriksaan gagal',
                              skipped: 'Kasus dilewati',
                            }[item.status] ||
                            item.status}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
            {report.run.status === 'completed' && (
              <section className={styles.panel}>
                <div className={styles.batchSummary}>
                  <h2 style={{ fontSize: 16 }}>Setelah rekomendasi ditinjau</h2>
                  <p>
                    Menyetujui rekomendasi belum mengubah program. Terapkan
                    perbaikan terlebih dahulu, lalu uji ulang pertanyaan yang
                    sama dengan bukti hasil evaluasi.
                  </p>
                  <details
                    className={styles.disclosure}
                    style={{ marginTop: 14 }}
                  >
                    <summary>Cara menjalankan uji ulang</summary>
                    <div>
                      <WorkerCommand
                        title="Uji ulang setelah perbaikan diterapkan"
                        description="Jalankan dari terminal backend. Pengujian memakai bukti yang sudah diverifikasi dan dapat memakai API LLM berbayar."
                        command={`python -m scripts.run_regression_evaluation --run-id ${report.run.run_id}`}
                      />
                    </div>
                  </details>
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
