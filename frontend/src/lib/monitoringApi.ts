import { adminFetch } from './adminApi';
import type {
  QueryLogRow, RequestDetail, LatencyHourlyRow, StageBreakdownDailyRow,
  ErrorStatsDailyRow, ErrorBreakdownDailyRow, OpenAIRetryStatsDailyRow,
  RetrievalQualityDailyRow, TopRetrievedDocumentRow, DomainStatsDailyRow,
  CostDailyRow, CostPerUserRow, ActiveUsersRow, NewVsReturningDailyRow,
  TurnsPerSessionDailyRow, FollowupRateDailyRow, AdminActivityDailyRow,
  SystemOverview, SessionStats,
} from './monitoringTypes';

async function metricsFetch<T>(path: string): Promise<{ data: T }> {
  return adminFetch<{ data: T }>(`/metrics${path}`, { method: 'GET' });
}

const qs = (params: Record<string, string | number | boolean | undefined>) => {
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined) usp.set(k, String(v));
  });
  const s = usp.toString();
  return s ? `?${s}` : '';
};

export const getSystemOverview = (days = 7) =>
  metricsFetch<SystemOverview | null>(`/system/overview${qs({ days })}`);

export const getLatencyStats = (days = 7) =>
  metricsFetch<LatencyHourlyRow[]>(`/latency${qs({ days })}`);

export const getStageBreakdown = (days = 7) =>
  metricsFetch<StageBreakdownDailyRow[]>(`/stage-breakdown${qs({ days })}`);

export const getErrorStats = (days = 7) =>
  metricsFetch<ErrorStatsDailyRow[]>(`/errors${qs({ days })}`);

export const getErrorBreakdown = (days = 7) =>
  metricsFetch<ErrorBreakdownDailyRow[]>(`/errors/breakdown${qs({ days })}`);

export const getOpenAIRetryStats = (days = 7) =>
  metricsFetch<OpenAIRetryStatsDailyRow[]>(`/openai-retry${qs({ days })}`);

export const getRetrievalQuality = (days = 7) =>
  metricsFetch<RetrievalQualityDailyRow[]>(`/retrieval-quality${qs({ days })}`);

export const getTopDocuments = (limit = 20) =>
  metricsFetch<TopRetrievedDocumentRow[]>(`/top-documents${qs({ limit })}`);

export const getDomainStats = (days = 7) =>
  metricsFetch<DomainStatsDailyRow[]>(`/domain-stats${qs({ days })}`);

export const getCostStats = (days = 7) =>
  metricsFetch<CostDailyRow[]>(`/cost${qs({ days })}`);

export const getCostPerUser = (limit = 50) =>
  metricsFetch<CostPerUserRow[]>(`/cost/per-user${qs({ limit })}`);

export const getActiveUsers = (granularity: 'daily' | 'monthly' = 'daily', days = 30) =>
  metricsFetch<ActiveUsersRow[]>(`/usage/active-users${qs({ granularity, days })}`);

export const getNewVsReturning = (days = 7) =>
  metricsFetch<NewVsReturningDailyRow[]>(`/usage/new-vs-returning${qs({ days })}`);

export const getTurnsPerSession = (days = 7) =>
  metricsFetch<TurnsPerSessionDailyRow[]>(`/usage/turns-per-session${qs({ days })}`);

export const getFollowupRate = (days = 7) =>
  metricsFetch<FollowupRateDailyRow[]>(`/usage/followup-rate${qs({ days })}`);

export const getAdminActivity = (days = 30) =>
  metricsFetch<AdminActivityDailyRow[]>(`/admin-activity${qs({ days })}`);

// F1: active session count vs MAX_ACTIVE_SESSIONS
export const getSystemHealth = () =>
  metricsFetch<{ session_stats: SessionStats; max_active_sessions: number; utilization_pct: number | null }>(`/system`);

// ---- Investigasi / drill-down ----
export const getQueryLog = (days = 7, limit = 500) =>
  metricsFetch<QueryLogRow[]>(`/query-log${qs({ days, limit })}`);

export const getRequestDetail = (requestId: string) =>
  metricsFetch<RequestDetail>(`/request/${encodeURIComponent(requestId)}`);
