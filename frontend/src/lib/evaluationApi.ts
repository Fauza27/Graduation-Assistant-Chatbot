import { adminFetch } from './adminApi';
import type {
  EvaluationCase,
  EvaluationRun,
  EvaluationRunReport,
  ReviewStatus,
} from './evaluationTypes';

interface CaseInput {
  request_id: string;
  review_status: ReviewStatus;
  expected_answer?: string;
  expected_evidence?: Record<string, unknown>;
  review_notes?: string;
}

export const createEvaluationCase = (input: CaseInput) =>
  adminFetch<{ data: EvaluationCase }>('/evaluations/cases', {
    method: 'POST',
    body: JSON.stringify(input),
  });

export const getEvaluationCases = () =>
  adminFetch<{ data: EvaluationCase[] }>('/evaluations/cases', { method: 'GET' });

export const getEvaluationCaseByRequest = (requestId: string) =>
  adminFetch<{ data: EvaluationCase | null }>(`/evaluations/cases/by-request/${requestId}`, {
    method: 'GET',
  });

export const getEvaluationRuns = () =>
  adminFetch<{ data: EvaluationRun[] }>('/evaluations/runs', { method: 'GET' });

export const getEvaluationRun = (runId: string) =>
  adminFetch<{ data: EvaluationRunReport }>(`/evaluations/runs/${runId}`, {
    method: 'GET',
  });

export const startEvaluationRun = (caseIds?: string[]) =>
  adminFetch<{ message: string; run_id: string; next_command: string }>('/evaluations/runs', {
    method: 'POST',
    body: JSON.stringify({ case_ids: caseIds || null }),
  });

export const reviewEvaluationRecommendation = (
  recommendationId: string,
  status: 'approved' | 'rejected',
) =>
  adminFetch<{ data: unknown }>(`/evaluations/recommendations/${recommendationId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
