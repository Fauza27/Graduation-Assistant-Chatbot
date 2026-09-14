-- Run once in the Supabase SQL editor before deploying the retrieval cache.
-- Existing documents and embeddings are preserved. Re-running is safe.
-- All workers read this revision before using a local retrieval cache entry.

BEGIN;

CREATE TABLE IF NOT EXISTS public.knowledge_base_revision (
    id smallint PRIMARY KEY CHECK (id = 1),
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0)
);

INSERT INTO public.knowledge_base_revision (id, revision)
VALUES (1, 0)
ON CONFLICT (id) DO NOTHING;

ALTER TABLE public.knowledge_base_revision ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.knowledge_base_revision FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON public.knowledge_base_revision TO service_role;

DROP POLICY IF EXISTS service_read_knowledge_revision ON public.knowledge_base_revision;
CREATE POLICY service_read_knowledge_revision ON public.knowledge_base_revision
    FOR SELECT TO service_role USING (true);

CREATE OR REPLACE FUNCTION public.bump_knowledge_base_revision()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    -- The increment commits or rolls back with the document mutation. UPDATE
    -- serializes concurrent increments, avoiding lost invalidations.
    UPDATE public.knowledge_base_revision
    SET revision = revision + 1
    WHERE id = 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Knowledge revision row is missing';
    END IF;
    RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION public.bump_knowledge_base_revision() FROM PUBLIC, anon, authenticated, service_role;

-- Statement triggers invalidate once per statement, including bulk edits and
-- truncation. Changes to embedding_status also change search eligibility.
DROP TRIGGER IF EXISTS child_documents_knowledge_revision ON public.child_documents;
CREATE TRIGGER child_documents_knowledge_revision
AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON public.child_documents
FOR EACH STATEMENT EXECUTE FUNCTION public.bump_knowledge_base_revision();

DROP TRIGGER IF EXISTS parent_documents_knowledge_revision ON public.parent_documents;
CREATE TRIGGER parent_documents_knowledge_revision
AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON public.parent_documents
FOR EACH STATEMENT EXECUTE FUNCTION public.bump_knowledge_base_revision();

-- Preserve the existing RPC signatures, ranking weights, filters and limits.
-- Only fully synchronized chunks may participate in any search branch.
CREATE OR REPLACE FUNCTION public.hybrid_search(
    query_text text,
    query_embedding public.vector,
    match_count integer DEFAULT 10,
    fts_weight double precision DEFAULT 0.3,
    vector_weight double precision DEFAULT 0.7,
    rrf_k integer DEFAULT 60,
    filter_section text DEFAULT NULL,
    filter_source text DEFAULT NULL
)
RETURNS TABLE (
    id text, parent_id text, title text, content text, section text,
    pages text[], source text, metadata jsonb, fts_rank double precision,
    vector_rank double precision, rrf_score double precision
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH fts_results AS (
        SELECT
            cd.id,
            ROW_NUMBER() OVER (
                ORDER BY ts_rank(
                    to_tsvector('indonesian', cd.content),
                    websearch_to_tsquery('indonesian', query_text)
                ) DESC
            ) AS rank_ix
        FROM public.child_documents cd
        WHERE cd.embedding_status = 'success'
            AND to_tsvector('indonesian', cd.content) @@ websearch_to_tsquery('indonesian', query_text)
            AND (filter_section IS NULL OR cd.section ILIKE '%' || filter_section || '%')
            AND (filter_source IS NULL OR cd.source = filter_source)
        ORDER BY rank_ix
        LIMIT match_count * 2
    ),
    vector_results AS (
        SELECT
            cd.id,
            ROW_NUMBER() OVER (
                ORDER BY cd.embedding <=> query_embedding
            ) AS rank_ix
        FROM public.child_documents cd
        WHERE cd.embedding_status = 'success'
            AND cd.embedding IS NOT NULL
            AND (filter_section IS NULL OR cd.section ILIKE '%' || filter_section || '%')
            AND (filter_source IS NULL OR cd.source = filter_source)
        ORDER BY rank_ix
        LIMIT match_count * 2
    ),
    rrf_scores AS (
        SELECT
            COALESCE(fts.id, vec.id) AS id,
            COALESCE(1.0 / (rrf_k + fts.rank_ix), 0.0) AS fts_score,
            COALESCE(1.0 / (rrf_k + vec.rank_ix), 0.0) AS vector_score,
            (
                fts_weight * COALESCE(1.0 / (rrf_k + fts.rank_ix), 0.0)
                + vector_weight * COALESCE(1.0 / (rrf_k + vec.rank_ix), 0.0)
            ) AS combined
        FROM fts_results fts
        FULL OUTER JOIN vector_results vec ON fts.id = vec.id
    )
    SELECT
        cd.id,
        cd.parent_id,
        cd.title,
        cd.content,
        cd.section,
        cd.pages,
        cd.source,
        cd.metadata,
        rrf.fts_score::FLOAT AS fts_rank,
        rrf.vector_score::FLOAT AS vector_rank,
        rrf.combined::FLOAT AS rrf_score
    FROM rrf_scores rrf
    JOIN public.child_documents cd ON cd.id = rrf.id
    ORDER BY rrf.combined DESC
    LIMIT match_count;
END;
$$;

CREATE OR REPLACE FUNCTION public.match_child_documents(
    query_embedding public.vector,
    match_threshold double precision DEFAULT 0.0,
    match_count integer DEFAULT 10,
    filter_section text DEFAULT NULL,
    filter_source text DEFAULT NULL
)
RETURNS TABLE (
    id text, parent_id text, title text, content text, section text,
    pages text[], source text, metadata jsonb, similarity double precision
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        cd.id,
        cd.parent_id,
        cd.title,
        cd.content,
        cd.section,
        cd.pages,
        cd.source,
        cd.metadata,
        1 - (cd.embedding <=> query_embedding) AS similarity
    FROM public.child_documents cd
    WHERE cd.embedding_status = 'success'
        AND cd.embedding IS NOT NULL
        AND (1 - (cd.embedding <=> query_embedding)) > match_threshold
        AND (filter_section IS NULL OR cd.section ILIKE '%' || filter_section || '%')
        AND (filter_source IS NULL OR cd.source = filter_source)
    ORDER BY cd.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

CREATE OR REPLACE FUNCTION public.match_documents(
    query_embedding public.vector,
    match_count integer DEFAULT 10
)
RETURNS TABLE (
    id text, content text, metadata jsonb, similarity double precision
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        cd.id,
        cd.content,
        cd.metadata,
        1 - (cd.embedding <=> query_embedding) AS similarity
    FROM public.child_documents cd
    WHERE cd.embedding_status = 'success'
        AND cd.embedding IS NOT NULL
    ORDER BY cd.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

CREATE OR REPLACE FUNCTION public.search_fts_child_documents(
    query_text text,
    match_count integer DEFAULT 10,
    filter_section text DEFAULT NULL,
    filter_source text DEFAULT NULL
)
RETURNS TABLE (
    id text, parent_id text, title text, content text, section text,
    pages text[], source text, metadata jsonb, fts_rank double precision
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        cd.id,
        cd.parent_id,
        cd.title,
        cd.content,
        cd.section,
        cd.pages,
        cd.source,
        cd.metadata,
        ts_rank(
            to_tsvector('indonesian', cd.content),
            websearch_to_tsquery('indonesian', query_text)
        )::FLOAT AS fts_rank
    FROM public.child_documents cd
    WHERE cd.embedding_status = 'success'
        AND to_tsvector('indonesian', cd.content) @@ websearch_to_tsquery('indonesian', query_text)
        AND (filter_section IS NULL OR cd.section ILIKE '%' || filter_section || '%')
        AND (filter_source IS NULL OR cd.source = filter_source)
    ORDER BY fts_rank DESC
    LIMIT match_count;
END;
$$;

COMMIT;
