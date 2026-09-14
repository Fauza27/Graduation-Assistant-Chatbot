-- ============================================================
-- Migrasi: Fungsi RPC FTS Fallback untuk Child Documents
-- Digunakan oleh hybrid_search.py saat OpenAI Embedding API
-- mengalami error / timeout, sehingga sistem tetap dapat melakukan
-- pencarian dokumen berbasis teks murni (Full-Text Search BM25).
-- ============================================================

CREATE OR REPLACE FUNCTION search_fts_child_documents(
    query_text     TEXT,
    match_count    INT DEFAULT 10,
    filter_section TEXT DEFAULT NULL,
    filter_source  TEXT DEFAULT NULL
)
RETURNS TABLE (
    id         TEXT,
    parent_id  TEXT,
    title      TEXT,
    content    TEXT,
    section    TEXT,
    pages      TEXT[],
    source     TEXT,
    metadata   JSONB,
    fts_rank   FLOAT
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
    FROM child_documents cd
    WHERE
        to_tsvector('indonesian', cd.content) @@ websearch_to_tsquery('indonesian', query_text)
        AND (filter_section IS NULL OR cd.section ILIKE '%' || filter_section || '%')
        AND (filter_source IS NULL OR cd.source = filter_source)
    ORDER BY fts_rank DESC
    LIMIT match_count;
END;
$$;
