-- =============================================================
-- Supabase Migration: Conversation Sessions Storage
-- Migrasi dari in-memory session store ke database-backed sessions
-- =============================================================

-- 1. Buat tabel conversation_sessions
-- ────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversation_sessions (
    session_id   TEXT PRIMARY KEY,                    -- Unique session identifier
    turns        JSONB NOT NULL DEFAULT '[]',         -- Array of conversation turns
    last_access  TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- Last access timestamp for TTL cleanup
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()   -- Session creation timestamp
);

-- 2. Indexes untuk performance
-- ─────────────────────────────
-- Index untuk cleanup idle sessions berdasarkan last_access
CREATE INDEX IF NOT EXISTS idx_sessions_last_access 
ON conversation_sessions (last_access);

-- Index untuk monitoring sessions berdasarkan created_at
CREATE INDEX IF NOT EXISTS idx_sessions_created_at 
ON conversation_sessions (created_at);

-- 3. Row Level Security
-- ──────────────────────
ALTER TABLE conversation_sessions ENABLE ROW LEVEL SECURITY;

-- Policy: Hanya service role yang bisa akses (konsisten dengan tabel lain)
DROP POLICY IF EXISTS "Service role can read conversation_sessions" ON conversation_sessions;
DROP POLICY IF EXISTS "Service role can write conversation_sessions" ON conversation_sessions;

CREATE POLICY "Service role can read conversation_sessions"
    ON conversation_sessions FOR SELECT
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role can write conversation_sessions"
    ON conversation_sessions FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- 4. Fungsi untuk cleanup idle sessions
-- ──────────────────────────────────────
CREATE OR REPLACE FUNCTION cleanup_idle_sessions(
    p_ttl_seconds INTEGER DEFAULT 3600  -- Default 1 hour TTL
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    -- Hapus sessions yang idle melebihi TTL
    DELETE FROM conversation_sessions
    WHERE last_access < NOW() - INTERVAL '1 second' * p_ttl_seconds;
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    
    -- Log hasil cleanup
    RAISE NOTICE 'Cleaned up % idle session(s) older than % seconds', v_deleted_count, p_ttl_seconds;
    
    RETURN v_deleted_count;
END;
$$;

-- 5. Fungsi untuk statistik sessions
-- ───────────────────────────────────
CREATE OR REPLACE FUNCTION get_session_statistics()
RETURNS TABLE (
    total_sessions INTEGER,
    active_sessions_1h INTEGER,
    active_sessions_24h INTEGER,
    avg_turns_per_session NUMERIC,
    oldest_session TIMESTAMPTZ,
    newest_session TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::INTEGER AS total_sessions,
        COUNT(CASE WHEN last_access >= NOW() - INTERVAL '1 hour' THEN 1 END)::INTEGER AS active_sessions_1h,
        COUNT(CASE WHEN last_access >= NOW() - INTERVAL '24 hours' THEN 1 END)::INTEGER AS active_sessions_24h,
        ROUND(AVG(jsonb_array_length(turns)), 2) AS avg_turns_per_session,
        MIN(created_at) AS oldest_session,
        MAX(created_at) AS newest_session
    FROM conversation_sessions;
END;
$$;

-- 6. Update settings table untuk session configuration
-- ─────────────────────────────────────────────────────
-- Tambah ke existing settings jika diperlukan
INSERT INTO user_quotas (user_id, date, message_count) 
VALUES ('_system_migration', '2024-05-20', 1)
ON CONFLICT (user_id, date) DO NOTHING;

-- Migration completed
SELECT 'Session storage migration completed successfully' AS status;