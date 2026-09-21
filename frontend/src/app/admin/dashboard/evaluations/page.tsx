'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowRight,
  BrainCircuit,
  ClipboardCheck,
  History,
  Inbox,
  LoaderCircle,
  Play,
  RefreshCw,
  Search,
} from 'lucide-react';
import {
  getEvaluationCases,
  getEvaluationRuns,
  startEvaluationRun,
} from '@/lib/evaluationApi';
import type {
  EvaluationCase,
  EvaluationRun,
  ReviewStatus,
} from '@/lib/evaluationTypes';
import {
  errorMessage,
  formatRunDate,
  isActiveRun,
  REVIEW_LABELS,
  RUN_LABELS,
} from '@/lib/evaluationUtils';
import CaseReview from '@/components/evaluation/CaseReview';
import {
  EmptyState,
  EvaluationDialog,
  StatusBadge,
  WorkerCommand,
} from '@/components/evaluation/EvaluationUI';
import styles from '@/components/evaluation/evaluation.module.css';

const PAGE_SIZE = 15;

export default function EvaluationsPage() {
  const [cases, setCases] = useState<EvaluationCase[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [tab, setTab] = useState<'queue' | 'history'>('queue');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<ReviewStatus | 'all'>('all');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<EvaluationCase | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<{
    run_id: string;
    next_command: string;
  } | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const allCheckbox = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    try {
      const [caseResponse, runResponse] = await Promise.all([
        getEvaluationCases(controller.signal),
        getEvaluationRuns(controller.signal),
      ]);
      if (controller.signal.aborted) return;
      setCases(caseResponse.data);
      setRuns(runResponse.data);
      setError(null);
      const available = new Set(caseResponse.data.map((item) => item.case_id));
      setSelected(
        (current) => new Set([...current].filter((id) => available.has(id))),
      );
    } catch (loadError) {
      if (!controller.signal.aborted) setError(errorMessage(loadError));
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    requestRef.current = controller;
    Promise.all([
      getEvaluationCases(controller.signal),
      getEvaluationRuns(controller.signal),
    ])
      .then(([caseResponse, runResponse]) => {
        if (controller.signal.aborted) return;
        setCases(caseResponse.data);
        setRuns(runResponse.data);
      })
      .catch((loadError) => {
        if (!controller.signal.aborted) setError(errorMessage(loadError));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const activeCount = runs.filter(isActiveRun).length;
  useEffect(() => {
    if (!activeCount) return;
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') void load();
    }, 15000);
    return () => clearInterval(timer);
  }, [activeCount, load]);

  const filtered = useMemo(() => {
    const term = search.trim().toLocaleLowerCase('id');
    return cases.filter(
      (item) =>
        (filter === 'all' || item.review_status === filter) &&
        (!term ||
          `${item.question} ${item.review_notes || ''}`
            .toLocaleLowerCase('id')
            .includes(term)),
    );
  }, [cases, search, filter]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const visibleCases = filtered.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );
  const allSelected =
    filtered.length > 0 && filtered.every((item) => selected.has(item.case_id));
  const someSelected = filtered.some((item) => selected.has(item.case_id));
  useEffect(() => {
    if (allCheckbox.current)
      allCheckbox.current.indeterminate = someSelected && !allSelected;
  }, [someSelected, allSelected]);

  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const toggleFiltered = () =>
    setSelected((current) => {
      const next = new Set(current);
      filtered.forEach((item) => {
        if (allSelected) next.delete(item.case_id);
        else next.add(item.case_id);
      });
      return next;
    });
  const queue = async () => {
    if (creating || !selected.size) return;
    setCreating(true);
    setError(null);
    try {
      const response = await startEvaluationRun([...selected]);
      setCreated(response);
      setConfirming(false);
      setSelected(new Set());
      await load();
    } catch (queueError) {
      setError(errorMessage(queueError));
      setConfirming(false);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.pageInner}>
        <header className={styles.header}>
          <div>
            <h1>
              <BrainCircuit size={25} aria-hidden="true" />
              Evaluasi RAG
            </h1>
            <p>Temukan penyebab jawaban gagal dan tinjau saran perbaikannya.</p>
          </div>
          <div className={styles.headerActions}>
            <Link
              className={styles.secondaryButton}
              href="/admin/dashboard/monitoring"
            >
              <ClipboardCheck size={16} />
              Nilai dari monitoring
            </Link>
            <button
              className={styles.secondaryButton}
              disabled={loading || creating}
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
          </div>
        </header>
        {error && (
          <div className={styles.error} role="alert">
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
          </div>
        )}
        <div className={styles.stats}>
          <div className={styles.stat}>
            <span className={styles.statIcon}>
              <Inbox size={21} />
            </span>
            <div>
              <strong>{loading && !cases.length ? '—' : cases.length}</strong>
              <p>Kasus dalam antrean</p>
            </div>
          </div>
          <div className={styles.stat}>
            <span className={styles.statIcon}>
              <ClipboardCheck size={21} />
            </span>
            <div>
              <strong>
                {loading && !cases.length
                  ? '—'
                  : cases.filter((item) => item.review_status === 'unreviewed')
                      .length}
              </strong>
              <p>Belum dinilai admin</p>
            </div>
          </div>
          <div className={styles.stat}>
            <span className={styles.statIcon}>
              <History size={21} />
            </span>
            <div>
              <strong>{loading && !runs.length ? '—' : activeCount}</strong>
              <p>Batch menunggu / berjalan</p>
            </div>
          </div>
        </div>
        <section className={styles.intro} aria-label="Alur evaluasi">
          <h2>Mulai dari kasus, lanjutkan ke perbaikan</h2>
          <ol className={styles.steps}>
            <li>
              <span>1</span>Periksa dan pilih kasus
            </li>
            <li>
              <span>2</span>Buat batch & jalankan worker
            </li>
            <li>
              <span>3</span>Tinjau hasil & uji perbaikan
            </li>
          </ol>
        </section>
        {created && (
          <section className={styles.panel}>
            <div className={styles.sectionHeader}>
              <div>
                <h2>Batch berhasil dibuat</h2>
                <p>Batch menunggu worker, belum menjalankan analisis.</p>
              </div>
              <Link
                className={styles.textLink}
                href={`/admin/dashboard/evaluations/${created.run_id}`}
              >
                Buka batch <ArrowRight size={15} />
              </Link>
            </div>
            <div className={styles.batchSummary}>
              <WorkerCommand command={created.next_command} />
            </div>
          </section>
        )}
        <section className={styles.panel}>
          <nav className={styles.tabs} aria-label="Tampilan evaluasi">
            <button
              className={styles.tab}
              aria-pressed={tab === 'queue'}
              onClick={() => setTab('queue')}
            >
              Antrean kasus <span>{cases.length}</span>
            </button>
            <button
              className={styles.tab}
              aria-pressed={tab === 'history'}
              onClick={() => setTab('history')}
            >
              Riwayat batch <span>{runs.length}</span>
            </button>
          </nav>
          {tab === 'queue' ? (
            <>
              <div className={styles.toolbar}>
                <label className={styles.search}>
                  <Search size={16} aria-hidden="true" />
                  <input
                    aria-label="Cari pertanyaan atau catatan"
                    value={search}
                    onChange={(event) => {
                      setSearch(event.target.value);
                      setPage(1);
                    }}
                    placeholder="Cari pertanyaan atau catatan…"
                  />
                </label>
                <select
                  className={styles.select}
                  aria-label="Filter kualitas jawaban"
                  value={filter}
                  onChange={(event) => {
                    setFilter(event.target.value as typeof filter);
                    setPage(1);
                  }}
                >
                  <option value="all">Semua status</option>
                  {(
                    [
                      'unreviewed',
                      'incorrect',
                      'incomplete',
                      'uncertain',
                    ] as const
                  ).map((status) => (
                    <option key={status} value={status}>
                      {REVIEW_LABELS[status]}
                    </option>
                  ))}
                </select>
              </div>
              <div className={styles.selectionBar}>
                <span>
                  {selected.size
                    ? `${selected.size} kasus dipilih`
                    : 'Pilih kasus yang ingin dianalisis.'}
                </span>
                {selected.size > 0 && (
                  <button
                    className={styles.textButton}
                    onClick={() => setSelected(new Set())}
                  >
                    Hapus pilihan
                  </button>
                )}
                <button
                  className={styles.primaryButton}
                  disabled={!selected.size || loading || creating}
                  onClick={() => setConfirming(true)}
                >
                  <Play size={15} />
                  Buat batch{selected.size > 0 ? ` (${selected.size})` : ''}
                </button>
              </div>
              {loading && !cases.length ? (
                <p className={styles.loading} role="status">
                  <LoaderCircle className={styles.spin} size={18} />
                  Memuat antrean…
                </p>
              ) : filtered.length ? (
                <>
                  <div className={styles.tableWrap}>
                    <table className={styles.table}>
                      <thead>
                        <tr>
                          <th>
                            <input
                              ref={allCheckbox}
                              type="checkbox"
                              checked={allSelected}
                              onChange={toggleFiltered}
                              aria-label="Pilih semua kasus sesuai filter, termasuk halaman lain"
                            />
                          </th>
                          <th>Pertanyaan</th>
                          <th>Penilaian</th>
                          <th className={styles.sourceColumn}>Asal kasus</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visibleCases.map((item) => (
                          <tr key={item.case_id}>
                            <td>
                              <input
                                type="checkbox"
                                checked={selected.has(item.case_id)}
                                onChange={() => toggle(item.case_id)}
                                aria-label={`Pilih kasus: ${item.question}`}
                              />
                            </td>
                            <td>
                              <button
                                className={styles.questionButton}
                                onClick={() => setReviewing(item)}
                              >
                                {item.question}
                              </button>
                              <p className={styles.sourceText}>
                                {item.review_notes ||
                                  'Klik pertanyaan untuk memeriksa dan menilai jawaban.'}
                              </p>
                            </td>
                            <td>
                              <StatusBadge
                                status={item.review_status}
                                label={REVIEW_LABELS[item.review_status]}
                              />
                            </td>
                            <td className={styles.sourceColumn}>
                              {item.created_by?.startsWith('system:auto:')
                                ? 'Deteksi otomatis'
                                : 'Penilaian admin'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className={styles.pagination}>
                    <span>
                      {filtered.length} kasus · Halaman {currentPage} dari{' '}
                      {pageCount}
                    </span>
                    <div className={styles.headerActions}>
                      <button
                        className={styles.secondaryButton}
                        disabled={currentPage <= 1}
                        onClick={() => setPage(currentPage - 1)}
                      >
                        Sebelumnya
                      </button>
                      <button
                        className={styles.secondaryButton}
                        disabled={currentPage >= pageCount}
                        onClick={() => setPage(currentPage + 1)}
                      >
                        Berikutnya
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <EmptyState
                  title={
                    cases.length
                      ? 'Tidak ada kasus yang cocok'
                      : 'Antrean masih kosong'
                  }
                >
                  {cases.length ? (
                    'Coba kata pencarian atau filter status lainnya.'
                  ) : (
                    <>
                      Kasus gagal dapat terdeteksi otomatis atau ditandai dari{' '}
                      <Link
                        className={styles.textLink}
                        href="/admin/dashboard/monitoring"
                      >
                        halaman monitoring
                      </Link>
                      .
                    </>
                  )}
                </EmptyState>
              )}
            </>
          ) : (
            <>
              <div className={styles.sectionHeader}>
                <div>
                  <h2>Batch evaluasi terbaru</h2>
                  <p>
                    Status menunggu berarti worker belum berjalan. Status
                    diperbarui otomatis selama halaman aktif.
                  </p>
                </div>
              </div>
              {loading && !runs.length ? (
                <p className={styles.loading} role="status">
                  Memuat riwayat…
                </p>
              ) : runs.length ? (
                <div className={styles.runList}>
                  {runs.map((run) => (
                    <Link
                      className={styles.runCard}
                      key={run.run_id}
                      href={`/admin/dashboard/evaluations/${run.run_id}`}
                    >
                      <div>
                        <div className={styles.runMeta}>
                          <StatusBadge
                            status={run.status}
                            label={RUN_LABELS[run.status]}
                          />
                          <strong>
                            {run.processed_cases} / {run.total_cases} kasus
                          </strong>
                        </div>
                        <small>
                          {formatRunDate(run.created_at)} ·{' '}
                          {run.evaluator_model}
                        </small>
                        <p className={styles.sourceText}>
                          Batch {run.run_id.slice(0, 8)}
                          {run.error_message ? ' · Ada kendala pemrosesan' : ''}
                        </p>
                      </div>
                      <ArrowRight size={17} aria-hidden="true" />
                    </Link>
                  ))}
                </div>
              ) : (
                <EmptyState title="Belum ada batch">
                  Pilih kasus dari antrean, lalu buat batch pertama.
                </EmptyState>
              )}
            </>
          )}
        </section>
        {reviewing && (
          <EvaluationDialog
            title="Periksa kasus evaluasi"
            onClose={() => setReviewing(null)}
          >
            <h3 className={styles.reason}>{reviewing.question}</h3>
            <CaseReview
              key={reviewing.case_id}
              requestId={reviewing.request_id}
              initialCase={reviewing}
              onSaved={() => void load()}
            />
          </EvaluationDialog>
        )}
        {confirming && (
          <EvaluationDialog
            title="Buat batch evaluasi?"
            onClose={() => setConfirming(false)}
            busy={creating}
          >
            <p className={styles.reason}>
              <strong>{selected.size} kasus akan dimasukkan ke batch.</strong>
              Analisis membandingkan dokumen asli dengan hasil pipeline. Proses
              dapat memakai API LLM berbayar.
            </p>
            <p className={styles.hint}>
              Membuat batch belum menjalankan agent. Setelah berhasil, salin
              perintah worker dan jalankan di terminal backend. Tidak ada
              scheduler otomatis.
            </p>
            <div className={styles.formActions}>
              <button
                className={styles.secondaryButton}
                disabled={creating}
                onClick={() => setConfirming(false)}
              >
                Batal
              </button>
              <button
                className={styles.primaryButton}
                disabled={creating}
                onClick={() => void queue()}
              >
                {creating ? (
                  <LoaderCircle className={styles.spin} size={16} />
                ) : (
                  <Play size={16} />
                )}
                {creating ? 'Membuat batch…' : 'Buat batch'}
              </button>
            </div>
          </EvaluationDialog>
        )}
      </div>
    </div>
  );
}
