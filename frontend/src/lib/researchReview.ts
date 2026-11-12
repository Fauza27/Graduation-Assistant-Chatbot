import { adminFetch } from './adminApi';
import type { CitationSource } from './store';

export type Disposition = 'pending' | 'study' | 'practice' | 'test';
export type Period = { start: string; end: string; code: string };
export type Participant = { code: string; consented_at: string };
export type Turn = {
  id: number;
  request_id: string;
  occurred_at: string;
  session_code: string;
  participant_code: string;
  question: string;
  answer: string | null;
  sources: CitationSource[];
  status: string;
  http_status: number | null;
  error_source: string | null;
  total_ms: number | null;
  disposition: Disposition;
  reviewed_question?: string | null;
  reviewed_answer?: string | null;
};
export type ContextTurn = Pick<Turn, 'id' | 'request_id' | 'occurred_at' | 'question' | 'answer' | 'disposition'>;
export type Page<T> = { data: T[]; next_before: number | null };
export type Review = {
  disposition: Disposition;
  reviewed_question: string | null;
  reviewed_answer: string | null;
};

export const loadParticipants = () =>
  adminFetch<{ data: Participant[] }>('/research/participants', { cache: 'no-store' });

export const enrollParticipant = (email: string, code: string) =>
  adminFetch<{ data: Participant }>('/research/participants', {
    method: 'POST', body: JSON.stringify({ email, code, confirmed: true }),
  });

export const loadTurns = (period: Period, before: number | null = null, exportOnly = false) => {
  const query = new URLSearchParams({ start: period.start, end: period.end });
  if (period.code) query.set('code', period.code);
  if (before !== null) query.set('before', String(before));
  return adminFetch<Page<Turn>>('/research/' + (exportOnly ? 'export?' : 'turns?') + query, { cache: 'no-store' });
};

export const loadContext = (id: string, before: number | null = null) =>
  adminFetch<Page<ContextTurn>>('/research/turns/' + id + '/context' + (before === null ? '' : '?before=' + before), {
    cache: 'no-store',
  });

export const saveReview = (id: string, review: Review) =>
  adminFetch<{ data: Review }>('/research/turns/' + id, {
    method: 'PATCH', body: JSON.stringify(review),
  });

function csvCell(value: string | number | null) {
  const text = String(value ?? '');
  const escapedFormula = typeof value === 'string' && (/^\s*[=+\-@]/u.test(text) || /^[\t\r\n]/u.test(text))
    ? "'" + text
    : text;
  return '"' + escapedFormula.replaceAll('"', '""') + '"';
}

export function buildResearchCsv(turns: Turn[]) {
  const rows: (string | number | null)[][] = [
    ['ID Pesan', 'Kode Peserta', 'Kode Sesi', 'Waktu (ISO 8601)', 'Pertanyaan',
      'Jawaban', 'Sumber (JSON)', 'Status', 'HTTP', 'Sumber Error', 'Durasi Backend (ms)'],
    ...turns.map(turn => [
      turn.request_id, turn.participant_code, turn.session_code, turn.occurred_at, turn.question,
      turn.answer, JSON.stringify(turn.sources), turn.status, turn.http_status, turn.error_source, turn.total_ms,
    ]),
  ];
  return '\uFEFF' + rows.map(row => row.map(csvCell).join(',')).join('\r\n');
}
