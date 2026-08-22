# Pseudocode untuk `scripts/supabase_migration_observability_views.sql`

```markdown
ALGORITMA SQL VIEWS AGREGASI MONITORING (supabase_migration_observability_views.sql)

Mendefinisikan views read-only untuk dashboard monitoring. Semua views
menggunakan CREATE OR REPLACE VIEW (idempoten, aman dijalankan berkali-kali).

DAFTAR VIEWS DAN FUNGSINYA:

1. v_latency_stats_hourly (A1, A3)
   - Granularitas: per JAM, digroup per channel
   - Metrics: total_requests, p50_ms, p95_ms, p99_ms, avg_ms
   - Filter: hanya status = 'success'
   - Pakai WITHIN GROUP untuk percentile_cont

2. v_stage_breakdown_daily (A2)
   - Granularitas: per HARI
   - Metrics: avg_*_ms untuk semua 9 tahap pipeline
   - Filter: hanya status = 'success'
   - Berguna untuk analisis bottleneck tahap mana paling lambat

3. v_error_stats_daily (B1, B4)
   - Granularitas: per HARI
   - Metrics: total_requests, error_count, quota_rejected_count,
             error_rate_pct, quota_rejection_rate_pct
   - Filter: SEMUA status (termasuk error dan quota_rejected)

4. v_error_breakdown_daily (B2)
   - Granularitas: per HARI, digroup per error_source
   - Metrics: error_count per sumber error
   - Filter: hanya status = 'error'
   - Berguna untuk tahu "OpenAI vs Supabase yang lebih sering error"

5. v_openai_retry_stats_daily (B3)
   - Granularitas: per HARI
   - Metrics: avg_retry_per_request, pct_requests_with_retry
   - Filter: hanya status = 'success'

6. v_retrieval_quality_daily (C1, C3, C4)
   - Granularitas: per HARI
   - Metrics: total_queries, no_relevant_doc_count, no_relevant_doc_pct,
             avg_docs_after_rerank, avg_top_score, avg_score_all_docs

7. v_top_retrieved_documents (C2)
   - Semua waktu (no time filter)
   - Pakai unnest(retrieved_parent_ids) untuk expand array ke baris
   - Metrics: parent_id, times_retrieved
   - ORDER BY times_retrieved DESC

8. v_domain_stats_daily (C5)
   - Granularitas: per HARI, digroup per domain
   - Metrics: total_queries, failed_retrieval_count, failed_retrieval_pct
   - Berguna untuk tahu domain mana yang sering gagal retrieval

9. v_cost_daily (D2, D3)
   - Granularitas: per HARI
   - Metrics: total_llm_cost_usd, total_embedding_cost_usd, total_cost_usd,
             total_requests, cost_per_request_usd

10. v_cost_per_user (D3)
    - Digroup per mahasiswa_id
    - Metrics: total_cost_usd, total_requests
    - ORDER BY total_cost_usd DESC (user paling boros di atas)

11. v_cost_per_session (D3)
    - Digroup per session_id
    - Metrics: total_cost_usd, total_requests

12. v_active_users_daily (E1, E3)
    - Granularitas: per HARI, digroup per channel
    - Metrics: active_users = COUNT DISTINCT coalesce(mahasiswa_id, session_id)

13. v_active_users_monthly (E1)
    - Sama dengan v_active_users_daily tapi granularitas BULANAN

14. v_session_first_seen (helper view untuk E2)
    - Digroup per session_id
    - Metrics: first_seen = MIN(created_at)

15. v_new_vs_returning_daily (E2)
    - JOIN request_metrics dengan v_session_first_seen
    - Granularitas: per HARI
    - Metrics: requests_from_new_sessions, requests_from_returning_sessions
    - "Baru" = first_seen di hari yang sama dengan request

16. v_avg_turns_per_session_daily (E2)
    - Subquery: COUNT request per session per hari
    - AVG subquery tersebut per hari
    - Metrics: avg_turns_per_session

17. v_followup_rate_daily (E5)
    - Granularitas: per HARI
    - Metrics: followup_count, total_requests, followup_rate_pct
    - "Follow-up" = rewrite_method IS NOT NULL AND rewrite_method <> 'None'
    - CATATAN: Ini PROXY, bukan definisi sempurna follow-up

18. v_admin_activity_daily (F3)
    - JOIN chunk_edit_logs dengan admin_users
    - Granularitas: per HARI, per admin
    - Metrics: total_edits, successful_reembeds, failed_reembeds, in_progress

CATATAN TEKNIS:
   - Semua views menggunakan CREATE OR REPLACE VIEW (idempoten).
   - Semua views read-only, tidak ada yang memodifikasi data.
   - Views ini hanya berguna setelah tabel request_metrics terisi data.
   - Jalankan SETELAH migration tabel (supabase_migration_observability.sql).
```
