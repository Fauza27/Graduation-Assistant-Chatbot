BEGIN;

-- Keep the reason a case entered the evaluation queue separate from the
-- administrator's later correctness review.
ALTER TABLE public.evaluation_cases
    ADD COLUMN IF NOT EXISTS queue_reason text;

UPDATE public.evaluation_cases
SET queue_reason = CASE
    WHEN created_by = 'system:auto:retrieval_error' THEN 'retrieval_error'
    WHEN created_by = 'system:auto:all_candidates_rejected' THEN 'all_candidates_rejected'
    WHEN created_by = 'system:auto:no_relevant_document' THEN 'no_relevant_document'
    WHEN created_by = 'system:auto:answer_abstention' THEN 'answer_abstention'
    ELSE 'manual_admin'
END
WHERE queue_reason IS NULL;

ALTER TABLE public.evaluation_cases
    ALTER COLUMN queue_reason SET DEFAULT 'manual_admin',
    ALTER COLUMN queue_reason SET NOT NULL;

ALTER TABLE public.evaluation_cases
    DROP CONSTRAINT IF EXISTS evaluation_cases_queue_reason_check;

ALTER TABLE public.evaluation_cases
    ADD CONSTRAINT evaluation_cases_queue_reason_check
    CHECK (queue_reason IN (
        'manual_admin',
        'retrieval_error',
        'all_candidates_rejected',
        'no_relevant_document',
        'answer_abstention'
    ));

CREATE INDEX IF NOT EXISTS idx_evaluation_cases_queue_reason
    ON public.evaluation_cases(queue_reason, review_status, created_at DESC);

-- Backfill only clear abstentions that have a saved trace and no existing case.
-- The review status remains unreviewed because an abstention can be correct.
INSERT INTO public.evaluation_cases (
    request_id,
    question,
    actual_answer,
    review_status,
    queue_reason,
    review_notes,
    created_by
)
SELECT
    metrics.request_id,
    metrics.question,
    trace.answer,
    'unreviewed',
    'answer_abstention',
    'Ditambahkan dari trace historis karena jawaban menyatakan informasi tidak tersedia. Tinjau cakupan bukti terkait.',
    'system:auto:answer_abstention'
FROM public.request_metrics AS metrics
JOIN public.rag_execution_traces AS trace
    ON trace.request_id = metrics.request_id
LEFT JOIN public.evaluation_cases AS existing
    ON existing.request_id = metrics.request_id
WHERE metrics.status = 'success'
  AND coalesce(metrics.question, '') <> ''
  AND coalesce(trace.answer, '') ~* (
      'dokumen( yang)? saya miliki tidak|'
      || 'informasi( spesifik)? tidak (ada|tersedia|ditemukan)|'
      || 'tidak (ditemukan|tersedia|tercantum|memuat)|'
      || 'belum (ditemukan|tersedia)'
  )
  AND existing.case_id IS NULL
ON CONFLICT (request_id) DO NOTHING;

INSERT INTO public.app_schema_migrations (version, description)
VALUES (
    '2026092101',
    'Queue abstention responses for RAG evaluation and retain their trigger reason'
)
ON CONFLICT (version) DO UPDATE
SET description = EXCLUDED.description;

NOTIFY pgrst, 'reload schema';
COMMIT;
