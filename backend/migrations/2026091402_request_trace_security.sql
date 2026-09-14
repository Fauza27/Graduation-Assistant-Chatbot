BEGIN;

ALTER TABLE public.request_metrics
    ADD COLUMN IF NOT EXISTS trace_id text,
    ADD COLUMN IF NOT EXISTS provider_request_id text,
    ADD COLUMN IF NOT EXISTS prompt_injection_detected boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_request_metrics_trace_id
    ON public.request_metrics (trace_id)
    WHERE trace_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_request_metrics_prompt_injection
    ON public.request_metrics (created_at DESC)
    WHERE prompt_injection_detected = true;

COMMENT ON COLUMN public.request_metrics.trace_id IS
    'OpenTelemetry trace ID untuk korelasi request lintas komponen.';
COMMENT ON COLUMN public.request_metrics.provider_request_id IS
    'Request ID provider AI untuk investigasi tanpa menyimpan credential.';
COMMENT ON COLUMN public.request_metrics.prompt_injection_detected IS
    'True jika input atau dokumen memuat pola instruksi yang mencurigakan.';

INSERT INTO public.app_schema_migrations (version, description)
VALUES ('2026091402', 'Add tracing and prompt-security diagnostics')
ON CONFLICT (version) DO NOTHING;

COMMIT;
