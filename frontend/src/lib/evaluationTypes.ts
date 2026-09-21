export type ReviewStatus =
  'unreviewed' | 'correct' | 'incorrect' | 'incomplete' | 'uncertain';

export interface EvaluationCase {
  case_id: string;
  request_id: string | null;
  question: string;
  actual_answer: string | null;
  review_status: ReviewStatus;
  expected_answer: string | null;
  expected_evidence: Record<string, unknown> | null;
  review_notes: string | null;
  created_by: string | null;
}

export interface EvaluationRun {
  run_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  evaluator_model: string;
  total_cases: number;
  processed_cases: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface EvaluationFinding {
  finding_id: string;
  run_id: string;
  case_id: string;
  answer_available: boolean | null;
  failed_stage: string;
  root_cause: string;
  confidence: number;
  affected_chunk_ids: string[];
  diagnostics: Record<string, unknown>;
}

export interface EvaluationRecommendation {
  recommendation_id: string;
  finding_id: string;
  target: string;
  action: string;
  rationale: string;
  risk: 'low' | 'medium' | 'high';
  validation_plan: string;
  status: 'proposed' | 'approved' | 'rejected' | 'implemented' | 'verified';
}

export interface EvaluationEvidence {
  evidence_id: string;
  case_id: string;
  page_start: number | null;
  page_end: number | null;
  evidence_text: string;
  explanation: string | null;
  confidence: number;
  is_verified: boolean;
}

export interface EvaluationRunReport {
  run: EvaluationRun;
  cases: EvaluationCase[];
  case_statuses: Array<{
    case_id: string;
    status: string;
    error_message: string | null;
  }>;
  evidence: EvaluationEvidence[];
  findings: EvaluationFinding[];
  recommendations: EvaluationRecommendation[];
}
