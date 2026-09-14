BEGIN;

CREATE TABLE IF NOT EXISTS public.app_schema_migrations (
    version text PRIMARY KEY,
    description text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.source_documents (
    document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE,
    title text NOT NULL,
    domain text NOT NULL CHECK (domain IN ('PI', 'KKP', 'SKRIPSI', 'NON_SKRIPSI')),
    chunk_source text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.source_document_versions (
    version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES public.source_documents(document_id) ON DELETE CASCADE,
    version_label text NOT NULL,
    checksum_sha256 text NOT NULL,
    storage_path text NOT NULL,
    mime_type text NOT NULL DEFAULT 'application/pdf',
    page_count integer CHECK (page_count IS NULL OR page_count > 0),
    extraction_status text NOT NULL DEFAULT 'pending'
        CHECK (extraction_status IN ('pending', 'ready', 'failed')),
    extraction_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, checksum_sha256)
);

ALTER TABLE public.parent_documents
    ADD COLUMN IF NOT EXISTS source_document_version_id uuid
        REFERENCES public.source_document_versions(version_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS chunking_version text,
    ADD COLUMN IF NOT EXISTS sequence_no integer;

ALTER TABLE public.child_documents
    ADD COLUMN IF NOT EXISTS source_document_version_id uuid
        REFERENCES public.source_document_versions(version_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS chunking_version text,
    ADD COLUMN IF NOT EXISTS sequence_no integer;

-- request_id lama belum memiliki unique constraint. Beberapa data test historis
-- menggunakan UUID yang sama untuk request berbeda. Pertahankan baris pertama
-- dan beri UUID baru hanya kepada salinan berikutnya agar tidak ada row hilang.
WITH ranked_request_ids AS (
    SELECT
        id,
        row_number() OVER (
            PARTITION BY request_id
            ORDER BY created_at, id
        ) AS duplicate_position
    FROM public.request_metrics
)
UPDATE public.request_metrics AS metrics
SET request_id = gen_random_uuid()
FROM ranked_request_ids AS ranked
WHERE metrics.id = ranked.id
  AND ranked.duplicate_position > 1;

CREATE UNIQUE INDEX IF NOT EXISTS idx_request_metrics_request_id_unique
    ON public.request_metrics(request_id);

CREATE TABLE IF NOT EXISTS public.rag_execution_traces (
    request_id uuid PRIMARY KEY REFERENCES public.request_metrics(request_id) ON DELETE CASCADE,
    query_plan jsonb NOT NULL DEFAULT '{}'::jsonb,
    self_query_results jsonb NOT NULL DEFAULT '[]'::jsonb,
    search_candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
    parent_candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
    reranked_candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
    final_context jsonb NOT NULL DEFAULT '{}'::jsonb,
    answer text,
    pipeline_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.evaluation_cases (
    case_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid UNIQUE REFERENCES public.request_metrics(request_id) ON DELETE SET NULL,
    question text NOT NULL,
    actual_answer text,
    review_status text NOT NULL DEFAULT 'unreviewed'
        CHECK (review_status IN ('unreviewed', 'correct', 'incorrect', 'incomplete', 'uncertain')),
    expected_answer text,
    expected_evidence jsonb,
    review_notes text,
    created_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.evaluation_runs (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    evaluator_model text NOT NULL,
    configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
    total_cases integer NOT NULL DEFAULT 0,
    processed_cases integer NOT NULL DEFAULT 0,
    error_message text,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.evaluation_run_cases (
    run_id uuid NOT NULL REFERENCES public.evaluation_runs(run_id) ON DELETE CASCADE,
    case_id uuid NOT NULL REFERENCES public.evaluation_cases(case_id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message text,
    started_at timestamptz,
    completed_at timestamptz,
    PRIMARY KEY (run_id, case_id)
);

CREATE TABLE IF NOT EXISTS public.evaluation_evidence (
    evidence_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES public.evaluation_runs(run_id) ON DELETE CASCADE,
    case_id uuid NOT NULL REFERENCES public.evaluation_cases(case_id) ON DELETE CASCADE,
    version_id uuid REFERENCES public.source_document_versions(version_id) ON DELETE SET NULL,
    page_start integer,
    page_end integer,
    evidence_text text NOT NULL,
    explanation text,
    confidence numeric(5,4) CHECK (confidence BETWEEN 0 AND 1),
    is_verified boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.evaluation_findings (
    finding_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES public.evaluation_runs(run_id) ON DELETE CASCADE,
    case_id uuid NOT NULL REFERENCES public.evaluation_cases(case_id) ON DELETE CASCADE,
    answer_available boolean,
    failed_stage text NOT NULL CHECK (failed_stage IN (
        'information_unavailable', 'extraction', 'chunking', 'query_processing',
        'retrieval', 'parent_assembly', 'reranking', 'context_assembly',
        'generation', 'ambiguous', 'unknown'
    )),
    root_cause text NOT NULL,
    confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    affected_chunk_ids text[] NOT NULL DEFAULT '{}',
    diagnostics jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, case_id)
);

CREATE TABLE IF NOT EXISTS public.evaluation_recommendations (
    recommendation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id uuid NOT NULL REFERENCES public.evaluation_findings(finding_id) ON DELETE CASCADE,
    target text NOT NULL,
    action text NOT NULL,
    rationale text NOT NULL,
    risk text NOT NULL CHECK (risk IN ('low', 'medium', 'high')),
    validation_plan text NOT NULL,
    status text NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'approved', 'rejected', 'implemented', 'verified')),
    reviewed_by text,
    reviewed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.regression_results (
    result_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES public.evaluation_runs(run_id) ON DELETE CASCADE,
    case_id uuid NOT NULL REFERENCES public.evaluation_cases(case_id) ON DELETE CASCADE,
    baseline_request_id uuid REFERENCES public.request_metrics(request_id) ON DELETE SET NULL,
    replay_request_id uuid REFERENCES public.request_metrics(request_id) ON DELETE SET NULL,
    evidence_found boolean,
    evidence_rank integer,
    survived_reranker boolean,
    included_in_context boolean,
    answer_correct boolean,
    citation_correct boolean,
    notes text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_source_document_versions_document
    ON public.source_document_versions(document_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_evaluation_cases_status
    ON public.evaluation_cases(review_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_evaluation_runs_status
    ON public.evaluation_runs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_evaluation_evidence_case
    ON public.evaluation_evidence(run_id, case_id);
CREATE INDEX IF NOT EXISTS idx_evaluation_findings_stage
    ON public.evaluation_findings(failed_stage, created_at DESC);

ALTER TABLE public.source_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rag_execution_traces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_run_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.regression_results ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'source_documents', 'source_document_versions', 'rag_execution_traces',
        'evaluation_cases', 'evaluation_runs', 'evaluation_run_cases',
        'evaluation_evidence', 'evaluation_findings',
        'evaluation_recommendations', 'regression_results'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = table_name
              AND policyname = format('Service role manages %s', table_name)
        ) THEN
            EXECUTE format(
                'CREATE POLICY "Service role manages %1$s" ON public.%1$I '
                'FOR ALL TO service_role USING (true) WITH CHECK (true)',
                table_name
            );
        END IF;
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO service_role', table_name);
        EXECUTE format('REVOKE ALL ON public.%I FROM anon, authenticated', table_name);
    END LOOP;
END;
$$;

INSERT INTO public.app_schema_migrations (version, description)
VALUES ('2026091403', 'Add source document registry and RAG evaluation workflow')
ON CONFLICT (version) DO NOTHING;

COMMIT;
