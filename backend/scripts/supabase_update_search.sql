-- =======================================================================================
-- FILE: supabase_update_search.sql
-- TUJUAN: Mengupdate fungsi RPC pencarian untuk mendukung filter berdasarkan 'source'
-- =======================================================================================

-- 1. Fungsi: Vector Search Only (Fallback)
CREATE OR REPLACE FUNCTION match_child_documents(
    query_embedding   VECTOR(2000),
    match_threshold   FLOAT DEFAULT 0.0,
    match_count       INT DEFAULT 10,
    filter_section    TEXT DEFAULT NULL,
    filter_source     TEXT DEFAULT NULL
)
RETURNS TABLE (
    id          TEXT,
    parent_id   TEXT,
    title       TEXT,
    content     TEXT,
    section     TEXT,
    pages       TEXT[],
    source      TEXT,
    metadata    JSONB,
    similarity  FLOAT
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
    FROM child_documents cd
    WHERE
        cd.embedding IS NOT NULL
        AND (1 - (cd.embedding <=> query_embedding)) > match_threshold
        AND (filter_section IS NULL OR cd.section ILIKE '%' || filter_section || '%')
        AND (filter_source IS NULL OR cd.source = filter_source)
    ORDER BY cd.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;


-- 2. Fungsi: Hybrid Search (FTS + Vector dengan RRF)
CREATE OR REPLACE FUNCTION hybrid_search(
    query_text        TEXT,
    query_embedding   VECTOR(2000),
    match_count       INT DEFAULT 10,
    fts_weight        FLOAT DEFAULT 0.3,
    vector_weight     FLOAT DEFAULT 0.7,
    rrf_k             INT DEFAULT 60,
    filter_section    TEXT DEFAULT NULL,
    filter_source     TEXT DEFAULT NULL
)
RETURNS TABLE (
    id              TEXT,
    parent_id       TEXT,
    title           TEXT,
    content         TEXT,
    section         TEXT,
    pages           TEXT[],
    source          TEXT,
    metadata        JSONB,
    fts_rank        FLOAT,
    vector_rank     FLOAT,
    rrf_score       FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY

    -- Sub-query 1: Full-Text Search ranking
    WITH fts_results AS (
        SELECT
            cd.id,
            ROW_NUMBER() OVER (
                ORDER BY ts_rank(
                    to_tsvector('indonesian', cd.content),
                    websearch_to_tsquery('indonesian', query_text)
                ) DESC
            ) AS rank_ix
        FROM child_documents cd
        WHERE
            to_tsvector('indonesian', cd.content) @@ websearch_to_tsquery('indonesian', query_text)
            AND (filter_section IS NULL OR cd.section ILIKE '%' || filter_section || '%')
            AND (filter_source IS NULL OR cd.source = filter_source)
        ORDER BY rank_ix
        LIMIT match_count * 2
    ),

    -- Sub-query 2: Vector Search ranking
    vector_results AS (
        SELECT
            cd.id,
            ROW_NUMBER() OVER (
                ORDER BY cd.embedding <=> query_embedding
            ) AS rank_ix
        FROM child_documents cd
        WHERE
            cd.embedding IS NOT NULL
            AND (filter_section IS NULL OR cd.section ILIKE '%' || filter_section || '%')
            AND (filter_source IS NULL OR cd.source = filter_source)
        ORDER BY rank_ix
        LIMIT match_count * 2
    ),

    -- RRF: gabungkan kedua ranking
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

    -- Final: gabungkan dengan data child_documents
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
    JOIN child_documents cd ON cd.id = rrf.id
    ORDER BY rrf.combined DESC
    LIMIT match_count;

END;
$$;
