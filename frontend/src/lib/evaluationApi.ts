import { adminFetch } from './adminApi';
import type {
  EvaluationCase,
  EvaluationRun,
  EvaluationRunReport,
  EvaluationRecommendation,
  ReviewStatus,
} from './evaluationTypes';

export interface CaseInput {
  request_id: string;
  review_status: ReviewStatus;
  expected_answer?: string | null;
  expected_evidence?: Record<string, unknown> | null;
  review_notes?: string | null;
}

export const updateEvaluationCase = (
  caseId: string,
  input: Omit<CaseInput, 'request_id'>,
) =>
  adminFetch<{ data: EvaluationCase }>(
    `/evaluations/cases/${encodeURIComponent(caseId)}`,
    {
      method: 'PATCH',
      body: JSON.stringify(input),
    },
  );

export const createEvaluationCase = (input: CaseInput) =>
  adminFetch<{ data: EvaluationCase }>('/evaluations/cases', {
    method: 'POST',
    body: JSON.stringify(input),
  });

export const getEvaluationCases = (signal?: AbortSignal) =>
  adminFetch<{ data: EvaluationCase[] }>('/evaluations/cases', {
    method: 'GET',
    signal,
  });

export const getEvaluationCaseByRequest = (
  requestId: string,
  signal?: AbortSignal,
) =>
  adminFetch<{ data: EvaluationCase | null; answer?: string | null }>(
    `/evaluations/cases/by-request/${encodeURIComponent(requestId)}`,
    {
      method: 'GET',
      signal,
    },
  );

export const getEvaluationRuns = (signal?: AbortSignal) =>
  adminFetch<{ data: EvaluationRun[] }>('/evaluations/runs', {
    method: 'GET',
    signal,
  });

export const getEvaluationRun = (runId: string, signal?: AbortSignal) =>
  adminFetch<{ data: EvaluationRunReport }>(
    `/evaluations/runs/${encodeURIComponent(runId)}`,
    {
      method: 'GET',
      signal,
    },
  );

export const startEvaluationRun = (caseIds?: string[]) =>
  adminFetch<{ message: string; run_id: string; next_command: string }>(
    '/evaluations/runs',
    {
      method: 'POST',
      body: JSON.stringify({ case_ids: caseIds || null }),
    },
  );

export const reviewEvaluationRecommendation = (
  recommendationId: string,
  status: 'approved' | 'rejected',
) =>
  adminFetch<{ data: EvaluationRecommendation }>(
    `/evaluations/recommendations/${encodeURIComponent(recommendationId)}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    },
  );
