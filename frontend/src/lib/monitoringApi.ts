import { adminFetch } from "./adminApi";
import type {
  QueryLogRow,
  RequestDetail,
  LatencyHourlyRow,
  StageBreakdownDailyRow,
  ErrorStatsDailyRow,
  ErrorBreakdownDailyRow,
  OpenAIRetryStatsDailyRow,
  RetrievalQualityDailyRow,
  TopRetrievedDocumentRow,
  DomainStatsDailyRow,
  CostDailyRow,
  CostPerUserRow,
  ActiveUsersRow,
  NewVsReturningDailyRow,
  TurnsPerSessionDailyRow,
  FollowupRateDailyRow,
  AdminActivityDailyRow,
  SystemOverview,
  SessionStats,
} from "./monitoringTypes";

interface MetricsEnvelope<T> {
  data: T;
  error?: string;
}

const inFlightMetrics = new Map<string, Promise<MetricsEnvelope<unknown>>>();

/**
 * Deduplicate identical GET requests. React Strict Mode mounts effects twice
 * in development; sharing the in-flight promise keeps that behavior from
 * producing duplicate requests to Supabase.
 */
async function metricsFetch<T>(path: string): Promise<MetricsEnvelope<T>> {
  let request = inFlightMetrics.get(path);
  if (!request) {
    request = adminFetch<MetricsEnvelope<unknown>>(`/metrics${path}`, {
      method: "GET",
    });
    inFlightMetrics.set(path, request);
    void request.then(
      () => inFlightMetrics.delete(path),
      () => inFlightMetrics.delete(path),
    );
  }

  const response = (await request) as MetricsEnvelope<T>;
  if (response.error) throw new Error(response.error);
  return response;
}

async function metricsListFetch<T>(
  path: string,
): Promise<MetricsEnvelope<T[]>> {
  const response = await metricsFetch<unknown>(path);
  if (!Array.isArray(response.data)) {
    throw new Error(
      "Format data monitoring tidak valid. Muat ulang backend lalu coba lagi.",
    );
  }
  return { data: response.data as T[] };
}

const qs = (params: Record<string, string | number | boolean | undefined>) => {
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined) usp.set(k, String(v));
  });
  const s = usp.toString();
  return s ? `?${s}` : "";
};

export const getSystemOverview = (days = 7) =>
  metricsFetch<SystemOverview | null>(`/system/overview${qs({ days })}`);

export const getLatencyStats = (days = 7) =>
  metricsListFetch<LatencyHourlyRow>(`/latency${qs({ days })}`);

export const getStageBreakdown = (days = 7) =>
  metricsListFetch<StageBreakdownDailyRow>(`/stage-breakdown${qs({ days })}`);

export const getErrorStats = (days = 7) =>
  metricsListFetch<ErrorStatsDailyRow>(`/errors${qs({ days })}`);

export const getErrorBreakdown = (days = 7) =>
  metricsListFetch<ErrorBreakdownDailyRow>(`/errors/breakdown${qs({ days })}`);

export const getOpenAIRetryStats = (days = 7) =>
  metricsListFetch<OpenAIRetryStatsDailyRow>(`/openai-retry${qs({ days })}`);

export const getRetrievalQuality = (days = 7) =>
  metricsListFetch<RetrievalQualityDailyRow>(
    `/retrieval-quality${qs({ days })}`,
  );

export const getTopDocuments = (limit = 20) =>
  metricsListFetch<TopRetrievedDocumentRow>(`/top-documents${qs({ limit })}`);

export const getDomainStats = (days = 7) =>
  metricsListFetch<DomainStatsDailyRow>(`/domain-stats${qs({ days })}`);

export const getCostStats = (days = 7) =>
  metricsListFetch<CostDailyRow>(`/cost${qs({ days })}`);

export const getCostPerUser = (limit = 50) =>
  metricsListFetch<CostPerUserRow>(`/cost/per-user${qs({ limit })}`);

export const getActiveUsers = (
  granularity: "daily" | "monthly" = "daily",
  days = 30,
) =>
  metricsListFetch<ActiveUsersRow>(
    `/usage/active-users${qs({ granularity, days })}`,
  );

export const getNewVsReturning = (days = 7) =>
  metricsListFetch<NewVsReturningDailyRow>(
    `/usage/new-vs-returning${qs({ days })}`,
  );

export const getTurnsPerSession = (days = 7) =>
  metricsListFetch<TurnsPerSessionDailyRow>(
    `/usage/turns-per-session${qs({ days })}`,
  );

export const getFollowupRate = (days = 7) =>
  metricsListFetch<FollowupRateDailyRow>(`/usage/followup-rate${qs({ days })}`);

export const getAdminActivity = (days = 30) =>
  metricsListFetch<AdminActivityDailyRow>(`/admin-activity${qs({ days })}`);

// F1: active session count vs MAX_ACTIVE_SESSIONS
export const getSystemHealth = () =>
  metricsFetch<{
    session_stats: SessionStats;
    max_active_sessions: number;
    utilization_pct: number | null;
  }>(`/system`);

// ---- Investigasi / drill-down ----
export const getQueryLog = (days = 7, limit = 500) =>
  metricsListFetch<QueryLogRow>(`/query-log${qs({ days, limit })}`);

export const getRequestDetail = (requestId: string) =>
  metricsFetch<RequestDetail>(`/request/${encodeURIComponent(requestId)}`);
