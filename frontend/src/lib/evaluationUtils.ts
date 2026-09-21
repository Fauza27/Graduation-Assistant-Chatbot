import type { EvaluationRun, ReviewStatus } from './evaluationTypes';

export const REVIEW_LABELS: Record<ReviewStatus, string> = {
  unreviewed: 'Belum dinilai',
  correct: 'Benar',
  incorrect: 'Salah',
  incomplete: 'Tidak lengkap',
  uncertain: 'Belum pasti',
};

export const RUN_LABELS: Record<EvaluationRun['status'], string> = {
  pending: 'Menunggu worker',
  running: 'Sedang dianalisis',
  completed: 'Selesai',
  failed: 'Gagal / parsial',
  cancelled: 'Dibatalkan',
};

export const STAGE_LABELS: Record<string, string> = {
  information_unavailable: 'Informasi tidak tersedia',
  extraction: 'Ekstraksi dokumen',
  chunking: 'Pemotongan dokumen',
  query_processing: 'Pemrosesan query',
  retrieval: 'Pencarian dokumen',
  parent_assembly: 'Penyusunan parent',
  reranking: 'Reranking',
  context_assembly: 'Penyusunan konteks',
  generation: 'Pembuatan jawaban',
  ambiguous: 'Belum dapat dipastikan',
  unknown: 'Belum diketahui',
};

export const RECOMMENDATION_LABELS: Record<string, string> = {
  proposed: 'Perlu ditinjau',
  approved: 'Disetujui',
  rejected: 'Ditolak',
  implemented: 'Diterapkan',
  verified: 'Terverifikasi',
};

export const errorMessage = (error: unknown) =>
  error instanceof Error
    ? error.message
    : 'Terjadi kesalahan. Silakan coba kembali.';

const dateFormatter = new Intl.DateTimeFormat('id-ID', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

export function formatRunDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? 'Waktu tidak tersedia'
    : dateFormatter.format(date);
}

export const isActiveRun = (run: EvaluationRun) =>
  ['pending', 'running'].includes(run.status);

export function recommendationSummary(action: string): string {
  return (
    action.split('\n\nUsulan: ')[1]?.split('\n\n')[0]?.trim() || action.trim()
  );
}

export const workerCommand = (runId: string) =>
  `python -m scripts.run_failure_evaluation --run-id ${runId}`;
