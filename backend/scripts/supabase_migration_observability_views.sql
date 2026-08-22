-- ============================================================
-- Views agregasi untuk dashboard monitoring.
-- Semua view ini read-only, aman dijalankan berkali-kali (CREATE OR REPLACE).
-- ============================================================

-- A1, A3: Latency percentile + throughput per jam
CREATE OR REPLACE VIEW v_latency_stats_hourly AS
SELECT
    date_trunc('hour', created_at) AS bucket,
    channel,
    count(*)                                                       AS total_requests,
    percentile_cont(0.5)  WITHIN GROUP (ORDER BY total_ms)         AS p50_ms,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY total_ms)         AS p95_ms,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY total_ms)         AS p99_ms,
    round(avg(total_ms), 2)                                        AS avg_ms
FROM request_metrics
WHERE status = 'success'
GROUP BY 1, 2
ORDER BY 1 DESC;

-- A2: Rata-rata durasi tiap tahap pipeline per hari
CREATE OR REPLACE VIEW v_stage_breakdown_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    round(avg(stage_validation_ms), 2)      AS avg_validation_ms,
    round(avg(stage_session_load_ms), 2)    AS avg_session_load_ms,
    round(avg(stage_reformulation_ms), 2)   AS avg_reformulation_ms,
    round(avg(stage_embedding_ms), 2)       AS avg_embedding_ms,
    round(avg(stage_retrieval_ms), 2)       AS avg_retrieval_ms,
    round(avg(stage_reranking_ms), 2)       AS avg_reranking_ms,
    round(avg(stage_parent_assembly_ms), 2) AS avg_parent_assembly_ms,
    round(avg(stage_generation_ms), 2)      AS avg_generation_ms,
    round(avg(stage_db_save_ms), 2)         AS avg_db_save_ms
FROM request_metrics
WHERE status = 'success'
GROUP BY 1
ORDER BY 1 DESC;

-- B1, B4: Error rate & quota rejection rate per hari
CREATE OR REPLACE VIEW v_error_stats_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    count(*)                                                                   AS total_requests,
    count(*) FILTER (WHERE status = 'error')                                   AS error_count,
    count(*) FILTER (WHERE status = 'quota_rejected')                          AS quota_rejected_count,
    round(100.0 * count(*) FILTER (WHERE status = 'error') / NULLIF(count(*), 0), 2)           AS error_rate_pct,
    round(100.0 * count(*) FILTER (WHERE status = 'quota_rejected') / NULLIF(count(*), 0), 2)  AS quota_rejection_rate_pct
FROM request_metrics
GROUP BY 1
ORDER BY 1 DESC;

-- B2: Breakdown error by source
CREATE OR REPLACE VIEW v_error_breakdown_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    coalesce(error_source, 'unknown') AS error_source,
    count(*) AS error_count
FROM request_metrics
WHERE status = 'error'
GROUP BY 1, 2
ORDER BY 1 DESC, error_count DESC;

-- B3: Retry rate ke OpenAI (rata-rata retry per request, dan % request yang butuh >=1 retry)
CREATE OR REPLACE VIEW v_openai_retry_stats_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    round(avg(openai_retry_count), 3)                                                 AS avg_retry_per_request,
    round(100.0 * count(*) FILTER (WHERE openai_retry_count > 0) / NULLIF(count(*), 0), 2) AS pct_requests_with_retry
FROM request_metrics
WHERE status = 'success'
GROUP BY 1
ORDER BY 1 DESC;

-- C1, C3, C4: Kualitas retrieval per hari
CREATE OR REPLACE VIEW v_retrieval_quality_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    count(*)                                                                        AS total_queries,
    count(*) FILTER (WHERE is_no_relevant_doc)                                      AS no_relevant_doc_count,
    round(100.0 * count(*) FILTER (WHERE is_no_relevant_doc) / NULLIF(count(*), 0), 2) AS no_relevant_doc_pct,
    round(avg(num_docs_after_rerank), 2)                                             AS avg_docs_after_rerank,
    round(avg(top_cross_encoder_score), 4)                                           AS avg_top_score,
    round(avg(avg_cross_encoder_score), 4)                                           AS avg_score_all_docs
FROM request_metrics
WHERE status = 'success'
GROUP BY 1
ORDER BY 1 DESC;

-- C2: Dokumen (parent_id) paling sering diambil
CREATE OR REPLACE VIEW v_top_retrieved_documents AS
SELECT
    parent_id,
    count(*) AS times_retrieved
FROM request_metrics, unnest(retrieved_parent_ids) AS parent_id
WHERE status = 'success'
GROUP BY 1
ORDER BY times_retrieved DESC;

-- C5: Breakdown query per domain — mana paling sering ditanya & paling sering gagal retrieval
CREATE OR REPLACE VIEW v_domain_stats_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    coalesce(domain_detected, 'UNKNOWN') AS domain,
    count(*)                                                                     AS total_queries,
    count(*) FILTER (WHERE is_no_relevant_doc)                                   AS failed_retrieval_count,
    round(100.0 * count(*) FILTER (WHERE is_no_relevant_doc) / NULLIF(count(*), 0), 2) AS failed_retrieval_pct
FROM request_metrics
WHERE status = 'success'
GROUP BY 1, 2
ORDER BY 1 DESC, total_queries DESC;

-- D2, D3: Cost harian, cost per request
CREATE OR REPLACE VIEW v_cost_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    round(sum(llm_cost_usd), 6)                                          AS total_llm_cost_usd,
    round(sum(embedding_cost_usd), 6)                                    AS total_embedding_cost_usd,
    round(sum(coalesce(llm_cost_usd, 0) + coalesce(embedding_cost_usd, 0)), 6) AS total_cost_usd,
    count(*)                                                              AS total_requests,
    round(sum(coalesce(llm_cost_usd, 0) + coalesce(embedding_cost_usd, 0)) / NULLIF(count(*), 0), 6) AS cost_per_request_usd
FROM request_metrics
WHERE status = 'success'
GROUP BY 1
ORDER BY 1 DESC;

-- D3: Cost per user (mahasiswa)
CREATE OR REPLACE VIEW v_cost_per_user AS
SELECT
    mahasiswa_id,
    round(sum(coalesce(llm_cost_usd, 0) + coalesce(embedding_cost_usd, 0)), 6) AS total_cost_usd,
    count(*)                                                                    AS total_requests
FROM request_metrics
WHERE status = 'success' AND mahasiswa_id IS NOT NULL
GROUP BY 1
ORDER BY total_cost_usd DESC;

-- D3: Cost per session
CREATE OR REPLACE VIEW v_cost_per_session AS
SELECT
    session_id,
    round(sum(coalesce(llm_cost_usd, 0) + coalesce(embedding_cost_usd, 0)), 6) AS total_cost_usd,
    count(*)                                                                    AS total_requests
FROM request_metrics
WHERE status = 'success' AND session_id IS NOT NULL
GROUP BY 1
ORDER BY total_cost_usd DESC;

-- E1, E3: Active users harian per channel (proxy: mahasiswa_id kalau ada, kalau tidak pakai session_id — berlaku untuk Telegram)
CREATE OR REPLACE VIEW v_active_users_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    channel,
    count(DISTINCT coalesce(mahasiswa_id, session_id)) AS active_users
FROM request_metrics
WHERE status = 'success'
GROUP BY 1, 2
ORDER BY 1 DESC;

-- E1: Active users bulanan
CREATE OR REPLACE VIEW v_active_users_monthly AS
SELECT
    date_trunc('month', created_at) AS month,
    channel,
    count(DISTINCT coalesce(mahasiswa_id, session_id)) AS active_users
FROM request_metrics
WHERE status = 'success'
GROUP BY 1, 2
ORDER BY 1 DESC;

-- E2: Sesi baru vs lanjutan per hari
CREATE OR REPLACE VIEW v_session_first_seen AS
SELECT
    session_id,
    min(created_at) AS first_seen
FROM request_metrics
WHERE status = 'success' AND session_id IS NOT NULL
GROUP BY 1;

CREATE OR REPLACE VIEW v_new_vs_returning_daily AS
SELECT
    date_trunc('day', rm.created_at) AS day,
    count(*) FILTER (
        WHERE date_trunc('day', fs.first_seen) = date_trunc('day', rm.created_at)
    ) AS requests_from_new_sessions,
    count(*) FILTER (
        WHERE date_trunc('day', fs.first_seen) < date_trunc('day', rm.created_at)
    ) AS requests_from_returning_sessions
FROM request_metrics rm
JOIN v_session_first_seen fs ON fs.session_id = rm.session_id
WHERE rm.status = 'success'
GROUP BY 1
ORDER BY 1 DESC;

-- E2: Rata-rata turn (request) per sesi per hari
CREATE OR REPLACE VIEW v_avg_turns_per_session_daily AS
SELECT
    day,
    round(avg(turns_per_session), 2) AS avg_turns_per_session
FROM (
    SELECT
        date_trunc('day', created_at) AS day,
        session_id,
        count(*) AS turns_per_session
    FROM request_metrics
    WHERE status = 'success' AND session_id IS NOT NULL
    GROUP BY 1, 2
) t
GROUP BY 1
ORDER BY 1 DESC;

-- E5: Repeat/follow-up question rate (proxy via rewrite_method — lihat catatan di bawah)
CREATE OR REPLACE VIEW v_followup_rate_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    count(*) FILTER (WHERE rewrite_method IS NOT NULL AND rewrite_method <> 'None') AS followup_count,
    count(*)                                                                         AS total_requests,
    round(100.0 * count(*) FILTER (WHERE rewrite_method IS NOT NULL AND rewrite_method <> 'None') / NULLIF(count(*), 0), 2) AS followup_rate_pct
FROM request_metrics
WHERE status = 'success'
GROUP BY 1
ORDER BY 1 DESC;

-- F3: Aktivitas admin (chunk edit + re-embed) — tabel chunk_edit_logs SUDAH ADA,
-- ini cuma view agregasi di atasnya, join ke admin_users untuk nama admin.
CREATE OR REPLACE VIEW v_admin_activity_daily AS
SELECT
    date_trunc('day', cel.edited_at) AS day,
    au.username                      AS admin_username,
    count(*)                                              AS total_edits,
    count(*) FILTER (WHERE cel.status = 'success')        AS successful_reembeds,
    count(*) FILTER (WHERE cel.status = 'failed')          AS failed_reembeds,
    count(*) FILTER (WHERE cel.status IN ('pending', 'processing')) AS in_progress
FROM chunk_edit_logs cel
LEFT JOIN admin_users au ON au.admin_id = cel.admin_id
GROUP BY 1, 2
ORDER BY 1 DESC;