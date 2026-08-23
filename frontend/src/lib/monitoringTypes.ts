// Tipe data untuk fitur Monitoring admin panel.
// Field-field ini disalin PERSIS dari skema `request_metrics` dan view-view
// agregasi di backend (lihat backend/scripts/supabase_migration_observability*.sql
// dan backend/src/api/admin_metrics.py) — bukan tebakan.

export type Channel = 'website' | 'telegram' | 'unknown';
export type RequestStatus = 'success' | 'error' | 'quota_rejected';
export type ErrorSource = 'openai' | 'supabase' | 'validation' | 'rate_limit' | 'unknown' | null;
export type Domain = 'PI' | 'KKP' | 'SKRIPSI' | 'NON_SKRIPSI' | 'UNKNOWN' | null;

export const PIPELINE_STAGE_KEYS = [
  'stage_validation_ms',
  'stage_session_load_ms',
  'stage_embedding_ms',
  'stage_retrieval_ms',
  'stage_reranking_ms',
  'stage_parent_assembly_ms',
  'stage_generation_ms',
  'stage_db_save_ms',
] as const;

export type StageKey = (typeof PIPELINE_STAGE_KEYS)[number];

export const STAGE_LABELS: Record<StageKey, string> = {
  stage_validation_ms: 'Validation',
  stage_session_load_ms: 'Session Load',
  stage_embedding_ms: 'Query Embedding',
  stage_retrieval_ms: 'Hybrid Retrieval',
  stage_reranking_ms: 'Reranking',
  stage_parent_assembly_ms: 'Parent Assembly',
  stage_generation_ms: 'LLM Generation',
  stage_db_save_ms: 'DB Save',
};

// ---- Baris mentah dari /admin/metrics/query-log dan /admin/metrics/request/{id} ----
export interface QueryLogRow {
  request_id: string;
  created_at: string;
  session_id: string | null;
  mahasiswa_id: string | null;
  username: string | null;
  channel: Channel;
  question: string | null;
  domain_detected: Domain;
  status: RequestStatus;
  error_source: ErrorSource;
  error_type: string | null;
  total_ms: number | null;
  stage_validation_ms: number | null;
  stage_session_load_ms: number | null;
  stage_reformulation_ms: number | null;
  stage_embedding_ms: number | null;
  stage_retrieval_ms: number | null;
  stage_reranking_ms: number | null;
  stage_parent_assembly_ms: number | null;
  stage_generation_ms: number | null;
  stage_db_save_ms: number | null;
  num_docs_retrieved: number | null;
  num_docs_after_rerank: number | null;
  top_cross_encoder_score: number | null;
  avg_cross_encoder_score: number | null;
  is_no_relevant_doc: boolean;
}

export interface RetrievalDetailItem {
  parent_id: string;
  title: string;
  score: number;
  accepted: boolean;
}

// Response penuh dari /admin/metrics/request/{id} — semua kolom request_metrics
export interface RequestDetail extends QueryLogRow {
  http_status: number | null;
  retrieved_parent_ids: string[] | null;
  rewrite_method: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  embedding_tokens: number | null;
  llm_cost_usd: number | null;
  embedding_cost_usd: number | null;
  openai_retry_count: number;
  retrieval_detail: RetrievalDetailItem[] | null;
}

// ---- Hasil view agregasi (semua di-select("*") dari view Postgres) ----
export interface LatencyHourlyRow {
  bucket: string;
  channel: Channel;
  total_requests: number;
  p50_ms: number | null;
  p95_ms: number | null;
  p99_ms: number | null;
  avg_ms: number | null;
}

export interface StageBreakdownDailyRow {
  day: string;
  avg_validation_ms: number | null;
  avg_session_load_ms: number | null;
  avg_reformulation_ms: number | null;
  avg_embedding_ms: number | null;
  avg_retrieval_ms: number | null;
  avg_reranking_ms: number | null;
  avg_parent_assembly_ms: number | null;
  avg_generation_ms: number | null;
  avg_db_save_ms: number | null;
}

export interface ErrorStatsDailyRow {
  day: string;
  total_requests: number;
  error_count: number;
  quota_rejected_count: number;
  error_rate_pct: number;
  quota_rejection_rate_pct: number;
}

export interface ErrorBreakdownDailyRow {
  day: string;
  error_source: string;
  error_count: number;
}

export interface OpenAIRetryStatsDailyRow {
  day: string;
  avg_retry_per_request: number;
  pct_requests_with_retry: number;
}

export interface RetrievalQualityDailyRow {
  day: string;
  total_queries: number;
  no_relevant_doc_count: number;
  no_relevant_doc_pct: number;
  avg_docs_after_rerank: number | null;
  avg_top_score: number | null;
  avg_score_all_docs: number | null;
}

export interface TopRetrievedDocumentRow {
  parent_id: string;
  times_retrieved: number;
}

export interface DomainStatsDailyRow {
  day: string;
  domain: string;
  total_queries: number;
  failed_retrieval_count: number;
  failed_retrieval_pct: number;
}

export interface CostDailyRow {
  day: string;
  total_llm_cost_usd: number | null;
  total_embedding_cost_usd: number | null;
  total_cost_usd: number | null;
  total_requests: number;
  cost_per_request_usd: number | null;
  total_input_tokens: number | null;
  total_output_tokens: number | null;
}

export interface CostPerUserRow {
  mahasiswa_id: string;
  total_cost_usd: number;
  total_requests: number;
}

export interface ActiveUsersRow {
  day?: string;
  month?: string;
  channel: Channel;
  active_users: number;
}

export interface NewVsReturningDailyRow {
  day: string;
  requests_from_new_sessions: number;
  requests_from_returning_sessions: number;
}

export interface TurnsPerSessionDailyRow {
  day: string;
  avg_turns_per_session: number;
}

export interface FollowupRateDailyRow {
  day: string;
  followup_count: number;
  total_requests: number;
  followup_rate_pct: number;
}

export interface AdminActivityDailyRow {
  day: string;
  admin_username: string;
  total_edits: number;
  successful_reembeds: number;
  failed_reembeds: number;
  in_progress: number;
}

export interface SystemOverview {
  period_days: number;
  total_requests: number;
  success_rate_pct: number;
  avg_latency_ms: number;
  total_cost_usd: number;
  active_users: number;
}

export interface SessionStats {
  active_sessions?: number;
  total_sessions?: number;
  [key: string]: unknown;
}
