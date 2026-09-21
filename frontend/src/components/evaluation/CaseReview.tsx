'use client';

import Link from 'next/link';
import { useEffect, useState, type FormEvent } from 'react';
import { ArrowUpRight, Check, LoaderCircle } from 'lucide-react';
import {
  createEvaluationCase,
  getEvaluationCaseByRequest,
  updateEvaluationCase,
} from '@/lib/evaluationApi';
import type { EvaluationCase, ReviewStatus } from '@/lib/evaluationTypes';
import { errorMessage, REVIEW_LABELS } from '@/lib/evaluationUtils';
import styles from './evaluation.module.css';

interface CaseReviewProps {
  requestId: string | null;
  initialCase?: EvaluationCase;
  onSaved?: (item: EvaluationCase) => void;
}

const choices: ReviewStatus[] = [
  'correct',
  'incorrect',
  'incomplete',
  'uncertain',
];

export default function CaseReview({
  requestId,
  initialCase,
  onSaved,
}: CaseReviewProps) {
  const [item, setItem] = useState(initialCase);
  const [actualAnswer, setActualAnswer] = useState(
    initialCase?.actual_answer || null,
  );
  const [status, setStatus] = useState<ReviewStatus>(
    initialCase?.review_status || 'uncertain',
  );
  const [answer, setAnswer] = useState(initialCase?.expected_answer || '');
  const [evidence, setEvidence] = useState(
    String(initialCase?.expected_evidence?.notes || ''),
  );
  const [notes, setNotes] = useState(initialCase?.review_notes || '');
  const [loading, setLoading] = useState(Boolean(requestId && !initialCase));
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (initialCase || !requestId) return;
    const controller = new AbortController();
    getEvaluationCaseByRequest(requestId, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        setActualAnswer(
          response.data?.actual_answer || response.answer || null,
        );
        if (!response.data) return;
        setItem(response.data);
        setStatus(response.data.review_status);
        setAnswer(response.data.expected_answer || '');
        setEvidence(String(response.data.expected_evidence?.notes || ''));
        setNotes(response.data.review_notes || '');
      })
      .catch((loadError) => {
        if (!controller.signal.aborted) {
          setError(errorMessage(loadError));
          setLoadFailed(true);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [initialCase, requestId, retry]);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (saving || loading || (!item && !requestId)) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    const existingEvidence = item?.expected_evidence || {};
    const updatedEvidence = {
      ...existingEvidence,
      notes: evidence.trim() || null,
    };
    const input = {
      review_status: status,
      expected_answer: answer.trim() || null,
      expected_evidence: Object.values(updatedEvidence).some(
        (value) => value !== null && value !== '',
      )
        ? updatedEvidence
        : null,
      review_notes: notes.trim() || null,
    };
    try {
      const response = item
        ? await updateEvaluationCase(item.case_id, input)
        : await createEvaluationCase({ ...input, request_id: requestId! });
      setItem(response.data);
      setSaved(true);
      onSaved?.(response.data);
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  if (loading)
    return (
      <p className={styles.loading} role="status">
        <LoaderCircle className={styles.spin} size={18} />
        Memuat penilaian…
      </p>
    );
  if (loadFailed)
    return (
      <div className={styles.error} role="alert">
        {error}
        <button
          className={styles.textButton}
          onClick={() => {
            setLoadFailed(false);
            setLoading(true);
            setError(null);
            setRetry((current) => current + 1);
          }}
        >
          Muat ulang penilaian
        </button>
      </div>
    );

  return (
    <form
      onSubmit={(event) => void save(event)}
      className={styles.reviewForm}
      onChange={() => setSaved(false)}
    >
      {actualAnswer && (
        <details open className={styles.disclosure}>
          <summary>Lihat jawaban chatbot</summary>
          <p className={styles.answerText}>{actualAnswer}</p>
        </details>
      )}
      <p className={styles.hint}>
        Jawaban salah, tidak lengkap, atau belum pasti masuk antrean evaluasi.
        Jawaban benar dikeluarkan dari antrean.
      </p>
      <fieldset disabled={saving} className={styles.fieldset}>
        <legend>Kualitas jawaban</legend>
        <div className={styles.reviewChoices}>
          {choices.map((choice) => (
            <label key={choice} className={styles.reviewChoice}>
              <input
                type="radio"
                name="review-status"
                value={choice}
                checked={status === choice}
                onChange={() => setStatus(choice)}
              />
              {REVIEW_LABELS[choice]}
            </label>
          ))}
        </div>
      </fieldset>
      <label className={styles.field}>
        Jawaban yang diharapkan <span>Opsional</span>
        <textarea
          rows={3}
          maxLength={20000}
          value={answer}
          disabled={saving}
          onChange={(event) => setAnswer(event.target.value)}
          placeholder="Tuliskan jawaban yang seharusnya diberikan."
        />
      </label>
      <label className={styles.field}>
        Referensi atau bukti <span>Opsional</span>
        <textarea
          rows={2}
          maxLength={10000}
          value={evidence}
          disabled={saving}
          onChange={(event) => setEvidence(event.target.value)}
          placeholder="Contoh: Pedoman Non-Skripsi, halaman 19, bagian 3.2.2."
        />
      </label>
      <label className={styles.field}>
        Catatan penilaian <span>Opsional</span>
        <textarea
          rows={2}
          maxLength={10000}
          value={notes}
          disabled={saving}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Bagian yang salah atau belum terjawab."
        />
      </label>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      <div className={styles.formActions}>
        <button
          className={styles.primaryButton}
          type="submit"
          disabled={saving || (!item && !requestId) || status === 'unreviewed'}
        >
          {saving ? (
            <LoaderCircle className={styles.spin} size={16} />
          ) : (
            <Check size={16} />
          )}
          {saving ? 'Menyimpan…' : 'Simpan penilaian'}
        </button>
        <Link className={styles.textLink} href="/admin/dashboard/evaluations">
          Buka antrean <ArrowUpRight size={14} />
        </Link>
      </div>
      {saved && (
        <p className={styles.success} role="status">
          Penilaian tersimpan.{' '}
          {status === 'correct'
            ? 'Kasus tidak masuk antrean evaluasi.'
            : 'Kasus tersedia di antrean evaluasi.'}
        </p>
      )}
    </form>
  );
}
