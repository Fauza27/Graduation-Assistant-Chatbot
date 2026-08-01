-- =============================================================
-- Supabase Schema untuk RAG Pipeline
-- Panduan Penyusunan Penulisan Ilmiah (PI) Chatbot
-- =============================================================

-- 1. Aktifkan extensions yang dibutuhkan
-- ─────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;        -- pgvector untuk embedding
CREATE EXTENSION IF NOT EXISTS pg_trgm;       -- trigram untuk fuzzy text search

-- 2. Tabel Parent Documents
-- ─────────────────────────────
-- Menyimpan parent chunks (konteks penuh untuk LLM)
DROP TABLE IF EXISTS child_documents;
DROP TABLE IF EXISTS parent_documents;

CREATE TABLE parent_documents (
    parent_id   TEXT PRIMARY KEY,              -- e.g. "parent-001"
    title       TEXT NOT NULL,                 -- judul parent chunk
    content     TEXT NOT NULL,                 -- konten lengkap parent
    section     TEXT NOT NULL,                 -- e.g. "BAB II", "Lampiran"
    child_ids   TEXT[] NOT NULL DEFAULT '{}',  -- array child IDs
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Tabel Child Documents
-- ────────────────────────────
-- Menyimpan child chunks + embedding vector (untuk retrieval)
-- Kolom "metadata" (JSONB) diperlukan agar kompatibel dengan
-- LangChain SupabaseVectorStore & SelfQueryRetriever.
CREATE TABLE child_documents (
    id          TEXT PRIMARY KEY,              -- e.g. "pi-001"
    parent_id   TEXT NOT NULL REFERENCES parent_documents(parent_id),
    title       TEXT NOT NULL,                 -- judul child chunk
    content     TEXT NOT NULL,                 -- konten child
    section     TEXT NOT NULL,                 -- e.g. "BAB II > 2.1"
    pages       TEXT[] NOT NULL DEFAULT '{}',  -- array halaman
    source      TEXT NOT NULL DEFAULT '',      -- nama file sumber
    metadata    JSONB NOT NULL DEFAULT '{}',   -- metadata JSONB untuk LangChain filter
    embedding   VECTOR(2000),                 -- text-embedding-3-large = 3072 dim -> reduce ke 2000 karena limit dari supabase
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Indexes
-- ──────────────
-- IVFFlat index untuk vector similarity search
-- Untuk 82 dokumen, 10 lists sudah cukup
CREATE INDEX idx_child_embedding ON child_documents
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 10);

-- GIN index untuk full-text search (digunakan oleh hybrid search)
CREATE INDEX idx_child_content_fts ON child_documents
USING GIN (to_tsvector('indonesian', content));

-- GIN index untuk metadata JSONB (digunakan oleh SelfQueryRetriever)
CREATE INDEX idx_child_metadata ON child_documents
USING GIN (metadata);

-- B-tree index untuk parent lookup
CREATE INDEX idx_child_parent_id ON child_documents (parent_id);

-- Index untuk filter metadata
CREATE INDEX idx_child_section ON child_documents (section);

-- 5. Fungsi: match_documents (kompatibel dengan SupabaseVectorStore)
-- ──────────────────────────────────────────────────────────────────
-- Fungsi ini dipanggil oleh LangChain SupabaseVectorStore untuk
-- dense search. Format return sesuai harapan LangChain.
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding   VECTOR(2000),
    match_count       INT DEFAULT 10
)
RETURNS TABLE (
    id          TEXT,
    content     TEXT,
    metadata    JSONB,
    similarity  FLOAT
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
    FROM child_documents cd
    WHERE cd.embedding IS NOT NULL
    ORDER BY cd.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 6. Fungsi: match_child_documents (dense search dengan filter)
-- ─────────────────────────────────────────────────────────────
-- Dense search langsung dengan optional section filter
CREATE OR REPLACE FUNCTION match_child_documents(
    query_embedding   VECTOR(2000),
    match_threshold   FLOAT DEFAULT 0.0,
    match_count       INT DEFAULT 10,
    filter_section    TEXT DEFAULT NULL
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
    ORDER BY cd.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 7. Fungsi: Hybrid Search (FTS + Vector dengan RRF)
-- ────────────────────────────────────────────────────
-- Reciprocal Rank Fusion (RRF) menggabungkan ranking dari dua sumber:
-- - Full-Text Search (sparse/keyword)
-- - Vector Search (dense/semantic)
-- Formula RRF: score = Σ w / (k + rank_i) untuk setiap retrieval system
CREATE OR REPLACE FUNCTION hybrid_search(
    query_text        TEXT,                   -- query untuk FTS
    query_embedding   VECTOR(2000),           -- query embedding untuk vector search
    match_count       INT DEFAULT 10,         -- jumlah hasil
    fts_weight        FLOAT DEFAULT 0.3,      -- bobot FTS
    vector_weight     FLOAT DEFAULT 0.7,      -- bobot vector search
    rrf_k             INT DEFAULT 60,         -- konstanta RRF (default 60)
    filter_section    TEXT DEFAULT NULL        -- optional filter
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

-- 8. Row Level Security (opsional tapi recommended)
-- ──────────────────────────────────────────────────
ALTER TABLE parent_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE child_documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can read parent_documents"
    ON parent_documents FOR SELECT
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role can insert parent_documents"
    ON parent_documents FOR INSERT
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service role can read child_documents"
    ON child_documents FOR SELECT
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role can insert child_documents"
    ON child_documents FOR INSERT
    WITH CHECK (auth.role() = 'service_role');

CREATE TABLE IF NOT EXISTS user_quotas (
  user_id TEXT NOT NULL,
  date TEXT NOT NULL, -- Format: YYYY-MM-DD
  message_count INTEGER DEFAULT 0,
  PRIMARY KEY (user_id, date)
);

CREATE TABLE IF NOT EXISTS chat_logs (
  id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  user_id TEXT NOT NULL,
  username TEXT,
  question TEXT NOT NULL,
  answer TEXT
);

-- 9. RLS untuk user_quotas dan chat_logs
-- ──────────────────────────────────────────────────
-- Konsisten dengan kebijakan parent/child_documents: hanya service_role.
ALTER TABLE user_quotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role can read user_quotas" ON user_quotas;
DROP POLICY IF EXISTS "Service role can write user_quotas" ON user_quotas;
DROP POLICY IF EXISTS "Service role can read chat_logs" ON chat_logs;
DROP POLICY IF EXISTS "Service role can write chat_logs" ON chat_logs;

CREATE POLICY "Service role can read user_quotas"
    ON user_quotas FOR SELECT
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role can write user_quotas"
    ON user_quotas FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service role can read chat_logs"
    ON chat_logs FOR SELECT
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role can write chat_logs"
    ON chat_logs FOR INSERT
    WITH CHECK (auth.role() = 'service_role');

