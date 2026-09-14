BEGIN;

CREATE TABLE IF NOT EXISTS public.app_schema_migrations (
    version text PRIMARY KEY,
    description text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.auth_refresh_tokens (
    token_hash text PRIMARY KEY,
    subject_id text NOT NULL,
    role text NOT NULL CHECK (role IN ('mahasiswa', 'admin')),
    family_id text NOT NULL,
    token_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    replaced_by_hash text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT auth_refresh_tokens_replacement_fkey
        FOREIGN KEY (replaced_by_hash)
        REFERENCES public.auth_refresh_tokens(token_hash)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_subject
    ON public.auth_refresh_tokens (subject_id, role);
CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_expiry
    ON public.auth_refresh_tokens (expires_at)
    WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_family
    ON public.auth_refresh_tokens (family_id);

ALTER TABLE public.auth_refresh_tokens ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'auth_refresh_tokens'
          AND policyname = 'Service role manages refresh tokens'
    ) THEN
        CREATE POLICY "Service role manages refresh tokens"
            ON public.auth_refresh_tokens
            FOR ALL
            TO service_role
            USING (true)
            WITH CHECK (true);
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.rotate_refresh_token(
    p_current_hash text,
    p_new_hash text,
    p_subject_id text,
    p_role text,
    p_family_id text,
    p_token_payload jsonb,
    p_expires_at timestamptz
) RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    consumed_count integer;
BEGIN
    UPDATE public.auth_refresh_tokens
       SET revoked_at = now(), replaced_by_hash = p_new_hash
     WHERE token_hash = p_current_hash
       AND subject_id = p_subject_id
       AND role = p_role
       AND family_id = p_family_id
       AND revoked_at IS NULL
       AND expires_at > now();

    GET DIAGNOSTICS consumed_count = ROW_COUNT;
    IF consumed_count <> 1 THEN
        RETURN false;
    END IF;

    INSERT INTO public.auth_refresh_tokens (
        token_hash, subject_id, role, family_id, token_payload, expires_at
    ) VALUES (
        p_new_hash, p_subject_id, p_role, p_family_id, p_token_payload, p_expires_at
    );
    RETURN true;
END;
$$;

CREATE OR REPLACE FUNCTION public.revoke_refresh_token_family(p_family_id text)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    revoked_count integer;
BEGIN
    UPDATE public.auth_refresh_tokens
       SET revoked_at = COALESCE(revoked_at, now())
     WHERE family_id = p_family_id;
    GET DIAGNOSTICS revoked_count = ROW_COUNT;
    RETURN revoked_count;
END;
$$;

CREATE OR REPLACE FUNCTION public.revoke_refresh_token(p_token_hash text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    revoked_count integer;
BEGIN
    UPDATE public.auth_refresh_tokens
       SET revoked_at = COALESCE(revoked_at, now())
     WHERE token_hash = p_token_hash;
    GET DIAGNOSTICS revoked_count = ROW_COUNT;
    RETURN revoked_count = 1;
END;
$$;

REVOKE ALL ON FUNCTION public.rotate_refresh_token(text, text, text, text, text, jsonb, timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.revoke_refresh_token(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.revoke_refresh_token_family(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.rotate_refresh_token(text, text, text, text, text, jsonb, timestamptz) TO service_role;
GRANT EXECUTE ON FUNCTION public.revoke_refresh_token(text) TO service_role;
GRANT EXECUTE ON FUNCTION public.revoke_refresh_token_family(text) TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.auth_refresh_tokens TO service_role;
GRANT SELECT, INSERT ON public.app_schema_migrations TO service_role;
REVOKE ALL ON public.auth_refresh_tokens FROM anon, authenticated;
REVOKE ALL ON public.app_schema_migrations FROM anon, authenticated;

INSERT INTO public.app_schema_migrations (version, description)
VALUES ('2026091401', 'Add rotating opaque refresh tokens')
ON CONFLICT (version) DO NOTHING;

COMMIT;
