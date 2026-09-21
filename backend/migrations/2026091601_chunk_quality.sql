BEGIN;

CREATE TABLE IF NOT EXISTS public.app_schema_migrations (
    version text PRIMARY KEY,
    description text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.parent_documents
    ADD COLUMN IF NOT EXISTS chunking_version text,
    ADD COLUMN IF NOT EXISTS sequence_no integer;

ALTER TABLE public.child_documents
    ADD COLUMN IF NOT EXISTS published_content text,
    ADD COLUMN IF NOT EXISTS chunking_version text,
    ADD COLUMN IF NOT EXISTS sequence_no integer;

UPDATE public.child_documents AS child
SET published_content = child.content
FROM public.parent_documents AS parent
WHERE child.parent_id = parent.parent_id
  AND child.published_content IS NULL
  AND child.embedding_status = 'success'
  AND child.content <> ''
  AND strpos(parent.content, child.content) > 0
  AND strpos(
        substr(parent.content, strpos(parent.content, child.content) + 1),
        child.content
      ) = 0;

-- Keep the JSON compatibility view synchronized with the canonical columns.
UPDATE public.child_documents
SET metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
        'parent_id', parent_id,
        'title', title,
        'section', section,
        'pages', pages,
        'source', source
    ),
    updated_at = now()
WHERE metadata->>'parent_id' IS DISTINCT FROM parent_id
   OR metadata->>'title' IS DISTINCT FROM title
   OR metadata->>'section' IS DISTINCT FROM section
   OR metadata->'pages' IS DISTINCT FROM to_jsonb(pages)
   OR metadata->>'source' IS DISTINCT FROM source;

-- Section filters are prefixes. Prefix matching prevents BAB II from also
-- matching BAB III while retaining nested paths such as "BAB II > 2.5".
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
        SELECT cd.id,
            row_number() OVER (
                ORDER BY ts_rank(
                    to_tsvector('indonesian', cd.content),
                    websearch_to_tsquery('indonesian', query_text)
                ) DESC
            ) AS rank_ix
        FROM public.child_documents AS cd
        WHERE cd.embedding_status = 'success'
          AND to_tsvector('indonesian', cd.content)
              @@ websearch_to_tsquery('indonesian', query_text)
          AND (filter_section IS NULL OR cd.section ILIKE filter_section || '%')
          AND (filter_source IS NULL OR cd.source = filter_source)
        ORDER BY rank_ix
        LIMIT match_count * 2
    ),
    vector_results AS (
        SELECT cd.id,
            row_number() OVER (ORDER BY cd.embedding <=> query_embedding) AS rank_ix
        FROM public.child_documents AS cd
        WHERE cd.embedding_status = 'success'
          AND cd.embedding IS NOT NULL
          AND (filter_section IS NULL OR cd.section ILIKE filter_section || '%')
          AND (filter_source IS NULL OR cd.source = filter_source)
        ORDER BY rank_ix
        LIMIT match_count * 2
    ),
    rrf_scores AS (
        SELECT
            coalesce(fts.id, vec.id) AS id,
            coalesce(1.0 / (rrf_k + fts.rank_ix), 0.0) AS fts_score,
            coalesce(1.0 / (rrf_k + vec.rank_ix), 0.0) AS vector_score,
            fts_weight * coalesce(1.0 / (rrf_k + fts.rank_ix), 0.0)
                + vector_weight * coalesce(1.0 / (rrf_k + vec.rank_ix), 0.0)
                AS combined
        FROM fts_results AS fts
        FULL OUTER JOIN vector_results AS vec ON fts.id = vec.id
    )
    SELECT cd.id, cd.parent_id, cd.title, cd.content, cd.section,
        cd.pages, cd.source, cd.metadata,
        rrf.fts_score::float, rrf.vector_score::float, rrf.combined::float
    FROM rrf_scores AS rrf
    JOIN public.child_documents AS cd ON cd.id = rrf.id
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
    SELECT cd.id, cd.parent_id, cd.title, cd.content, cd.section,
        cd.pages, cd.source, cd.metadata,
        (1 - (cd.embedding <=> query_embedding))::float
    FROM public.child_documents AS cd
    WHERE cd.embedding_status = 'success'
      AND cd.embedding IS NOT NULL
      AND (1 - (cd.embedding <=> query_embedding)) > match_threshold
      AND (filter_section IS NULL OR cd.section ILIKE filter_section || '%')
      AND (filter_source IS NULL OR cd.source = filter_source)
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
    SELECT cd.id, cd.parent_id, cd.title, cd.content, cd.section,
        cd.pages, cd.source, cd.metadata,
        ts_rank(
            to_tsvector('indonesian', cd.content),
            websearch_to_tsquery('indonesian', query_text)
        )::float
    FROM public.child_documents AS cd
    WHERE cd.embedding_status = 'success'
      AND to_tsvector('indonesian', cd.content)
          @@ websearch_to_tsquery('indonesian', query_text)
      AND (filter_section IS NULL OR cd.section ILIKE filter_section || '%')
      AND (filter_source IS NULL OR cd.source = filter_source)
    ORDER BY fts_rank DESC
    LIMIT match_count;
END;
$$;

-- Publish one parent and all of its existing children in one transaction.
-- IDs must remain identical, preventing stale evaluation and edit references.
CREATE OR REPLACE FUNCTION public.replace_knowledge_parent_chunks(
    p_parent jsonb,
    p_children jsonb,
    p_chunking_version text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_parent_id text := p_parent->>'parent_id';
    v_domain text := p_parent->>'domain';
    v_child jsonb;
    v_embedding public.vector;
    v_expected_ids text[];
    v_received_ids text[];
    v_ordered_ids text[];
    v_parent_child_ids text[];
    v_parent_content text;
    v_updated_count integer := 0;
    v_row_count integer;
BEGIN
    IF v_parent_id IS NULL OR v_parent_id = '' THEN
        RAISE EXCEPTION 'parent_id is required' USING ERRCODE = '22023';
    END IF;
    IF jsonb_typeof(p_children) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'p_children must be an array' USING ERRCODE = '22023';
    END IF;

    PERFORM 1
    FROM public.parent_documents
    WHERE parent_id = v_parent_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Parent % not found', v_parent_id USING ERRCODE = 'P0002';
    END IF;

    SELECT array_agg(id ORDER BY id)
    INTO v_expected_ids
    FROM public.child_documents
    WHERE parent_id = v_parent_id;

    SELECT array_agg(item->>'id' ORDER BY item->>'id')
    INTO v_received_ids
    FROM jsonb_array_elements(p_children) AS rows(item);

    IF v_expected_ids IS DISTINCT FROM v_received_ids THEN
        RAISE EXCEPTION 'Child ID set differs for parent %', v_parent_id
            USING ERRCODE = '40001';
    END IF;

    SELECT array_agg(item->>'id' ORDER BY ordinality)
    INTO v_ordered_ids
    FROM jsonb_array_elements(p_children) WITH ORDINALITY AS rows(item, ordinality);

    SELECT array_agg(value ORDER BY ordinality)
    INTO v_parent_child_ids
    FROM jsonb_array_elements_text(p_parent->'child_ids')
        WITH ORDINALITY AS rows(value, ordinality);

    IF v_parent_child_ids IS DISTINCT FROM v_ordered_ids THEN
        RAISE EXCEPTION 'Parent child_ids order differs from children for %', v_parent_id
            USING ERRCODE = '22023';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.child_documents
        WHERE parent_id = v_parent_id AND embedding_status <> 'success'
    ) THEN
        RAISE EXCEPTION 'Parent % has a child with an unfinished edit or embedding',
            v_parent_id
            USING ERRCODE = '40001';
    END IF;

    SELECT string_agg(item->>'content', E'\n\n' ORDER BY ordinality)
    INTO v_parent_content
    FROM jsonb_array_elements(p_children) WITH ORDINALITY AS rows(item, ordinality);

    IF v_parent_content IS DISTINCT FROM p_parent->>'content' THEN
        RAISE EXCEPTION 'Parent content does not equal ordered child content for %', v_parent_id
            USING ERRCODE = '22023';
    END IF;

    UPDATE public.parent_documents
    SET title = p_parent->>'title',
        content = p_parent->>'content',
        section = p_parent->>'section',
        child_ids = ARRAY(
            SELECT jsonb_array_elements_text(p_parent->'child_ids')
        ),
        domain = v_domain,
        chunking_version = p_chunking_version,
        sequence_no = (p_parent->>'sequence_no')::integer,
        updated_at = now()
    WHERE parent_id = v_parent_id;

    FOR v_child IN SELECT value FROM jsonb_array_elements(p_children)
    LOOP
        v_embedding := (v_child->>'embedding')::public.vector;
        IF v_embedding IS NULL OR public.vector_dims(v_embedding) <> 2000 THEN
            RAISE EXCEPTION 'Embedding for child % must have 2000 dimensions', v_child->>'id'
                USING ERRCODE = '22023';
        END IF;

        UPDATE public.child_documents
        SET title = v_child->>'title',
            content = v_child->>'content',
            section = v_child->>'section',
            pages = ARRAY(SELECT jsonb_array_elements_text(v_child->'pages')),
            source = v_child->>'source',
            metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
                'parent_id', v_parent_id,
                'title', v_child->>'title',
                'section', v_child->>'section',
                'pages', v_child->'pages',
                'source', v_child->>'source'
            ),
            embedding = v_embedding,
            embedding_status = 'success',
            published_content = v_child->>'content',
            domain = v_domain,
            chunking_version = p_chunking_version,
            sequence_no = (v_child->>'sequence_no')::integer,
            updated_at = now()
        WHERE id = v_child->>'id'
          AND parent_id = v_parent_id;
        GET DIAGNOSTICS v_row_count = ROW_COUNT;
        IF v_row_count <> 1 THEN
            RAISE EXCEPTION 'Child % was not updated for parent %',
                v_child->>'id', v_parent_id USING ERRCODE = '40001';
        END IF;
        v_updated_count := v_updated_count + v_row_count;
    END LOOP;

    RETURN jsonb_build_object(
        'parent_id', v_parent_id,
        'updated_children', v_updated_count,
        'chunking_version', p_chunking_version
    );
END;
$$;

REVOKE ALL ON FUNCTION public.replace_knowledge_parent_chunks(jsonb, jsonb, text)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.replace_knowledge_parent_chunks(jsonb, jsonb, text)
    TO service_role;

INSERT INTO public.app_schema_migrations (version, description)
VALUES (
    '2026091601',
    'Lossless PI/KKP chunk publishing, metadata synchronization, and safe section prefixes'
)
ON CONFLICT (version) DO UPDATE
SET description = EXCLUDED.description;

NOTIFY pgrst, 'reload schema';
COMMIT;

SELECT
    count(*) FILTER (WHERE metadata->>'section' IS DISTINCT FROM section)
        AS remaining_section_mismatches,
    count(*) FILTER (WHERE published_content IS NULL)
        AS missing_published_content
FROM public.child_documents;
