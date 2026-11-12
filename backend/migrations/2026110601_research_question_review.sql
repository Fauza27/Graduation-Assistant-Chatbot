BEGIN;

CREATE TABLE IF NOT EXISTS public.research_participants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mahasiswa_id uuid UNIQUE NOT NULL REFERENCES public.mahasiswa_accounts(mahasiswa_id) ON DELETE CASCADE,
    code text UNIQUE NOT NULL CHECK (code ~ '^P-[0-9]{1,6}$'),
    consented_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.research_turns (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id uuid UNIQUE NOT NULL,
    participant_id uuid NOT NULL REFERENCES public.research_participants(id) ON DELETE CASCADE,
    occurred_at timestamptz NOT NULL,
    session_code text NOT NULL,
    question text NOT NULL,
    answer text,
    sources jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL,
    http_status integer,
    error_source text,
    total_ms numeric,
    disposition text NOT NULL DEFAULT 'pending'
        CHECK (disposition IN ('pending', 'study', 'practice', 'test')),
    reviewed_question text,
    reviewed_answer text,
    CHECK (
        disposition <> 'study'
        OR (
            nullif(btrim(reviewed_question), '') IS NOT NULL
            AND (answer IS NULL OR nullif(btrim(reviewed_answer), '') IS NOT NULL)
        )
    )
);

CREATE INDEX IF NOT EXISTS research_turns_period ON public.research_turns (occurred_at, id);
CREATE INDEX IF NOT EXISTS research_turns_context ON public.research_turns (participant_id, session_code, id);

ALTER TABLE public.research_participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_turns ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.research_participants, public.research_turns FROM PUBLIC, anon, authenticated;
REVOKE ALL ON SEQUENCE public.research_turns_id_seq FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, DELETE ON public.research_participants TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.research_turns TO service_role;
GRANT USAGE ON SEQUENCE public.research_turns_id_seq TO service_role;

CREATE OR REPLACE FUNCTION public.record_research_turn(
    p_account uuid, p_request uuid, p_started_at timestamptz, p_session text,
    p_question text, p_answer text, p_sources jsonb, p_status text,
    p_http_status integer, p_error_source text, p_total_ms numeric
)
RETURNS void
LANGUAGE sql
SECURITY INVOKER
SET search_path = ''
AS $$
    INSERT INTO public.research_turns (
        request_id, participant_id, occurred_at, session_code, question, answer,
        sources, status, http_status, error_source, total_ms
    )
    SELECT
        p_request, p.id, p_started_at, md5(p.id::text || ':' || p_session), p_question,
        p_answer, p_sources, p_status, p_http_status, p_error_source, p_total_ms
    FROM public.research_participants AS p
    WHERE p.mahasiswa_id = p_account AND p.consented_at <= p_started_at
    ON CONFLICT (request_id) DO NOTHING;
$$;

REVOKE ALL ON FUNCTION public.record_research_turn(uuid, uuid, timestamptz, text, text, text, jsonb, text, integer, text, numeric)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_research_turn(uuid, uuid, timestamptz, text, text, text, jsonb, text, integer, text, numeric)
    TO service_role;

INSERT INTO public.app_schema_migrations (version, description)
VALUES ('2026110601', 'Add consent-scoped question review')
ON CONFLICT (version) DO NOTHING;

COMMIT;
