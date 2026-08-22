# Pseudocode untuk `src/api/admin_metrics.py`

```markdown
ALGORITMA ENDPOINT ADMIN METRICS (admin_metrics.py)

Menyediakan REST API read-only untuk membaca hasil agregasi monitoring
dari SQL views. Semua endpoint butuh autentikasi admin (Bearer token).

1. INISIALISASI
   - APIRouter prefix="/admin/metrics", tags=["Admin Metrics"].
   - Router ini didaftarkan dengan prefix /api di application.py,
     sehingga endpoint final: /api/admin/metrics/*.
   
   - FUNGSI _get_supabase_client() (lru_cache):
     - Buat Supabase client sekali, cache untuk reuse.
   
   - FUNGSI _select_view(view_name, days, order_col="day"):
     - Hitung timestamp `since` = sekarang - timedelta(days=days).
     - Query view dengan filter gte(order_col, since).
     - Kembalikan list of dict dari hasil query.

2. ENDPOINTS (semua GET, semua require Depends(get_current_admin)):

   GET /latency
   - Query: days (default 7, max 90)
   - Data: v_latency_stats_hourly (A1/A3: latency percentile & throughput)
   - Kembalikan: {"data": [...]}

   GET /stage-breakdown
   - Query: days (default 30, max 180)
   - Data: v_stage_breakdown_daily (A2: rata-rata durasi tiap stage)

   GET /errors
   - Query: days (default 30, max 180)
   - Data: v_error_stats_daily (B1/B4: error rate & quota rejection)

   GET /errors/breakdown
   - Query: days (default 30, max 180)
   - Data: v_error_breakdown_daily (B2: breakdown error by source)

   GET /openai-retry
   - Query: days (default 30, max 180)
   - Data: v_openai_retry_stats_daily (B3: retry rate ke OpenAI)

   GET /retrieval-quality
   - Query: days (default 30, max 180)
   - Data: v_retrieval_quality_daily (C1/C3/C4: kualitas retrieval)

   GET /top-documents
   - Query: limit (default 20, max 100)
   - Data: v_top_retrieved_documents (C2: dokumen paling sering diambil)
   - NOTE: tidak ada filter days karena view ini all-time ranking.

   GET /domain-stats
   - Query: days (default 30, max 180)
   - Data: v_domain_stats_daily (C5: breakdown query per domain)

   GET /cost
   - Query: days (default 30, max 180)
   - Data: v_cost_daily (D2/D3: cost harian & cost per request)

   GET /cost/per-user
   - Query: limit (default 50, max 500)
   - Data: v_cost_per_user (D3: cost per mahasiswa)

   GET /usage/active-users
   - Query: granularity ("daily"|"monthly"), days (default 30, max 365)
   - Data: v_active_users_daily atau v_active_users_monthly (E1)

   GET /usage/new-vs-returning
   - Query: days (default 30, max 180)
   - Data: v_new_vs_returning_daily (E2)

   GET /usage/turns-per-session
   - Query: days (default 30, max 180)
   - Data: v_avg_turns_per_session_daily (E2)

   GET /usage/followup-rate
   - Query: days (default 30, max 180)
   - Data: v_followup_rate_daily (E5)

   GET /admin-activity
   - Query: days (default 30, max 180)
   - Data: v_admin_activity_daily (F3)

   GET /system/overview
   - Query: days (default 7, max 30)
   - Menggabungkan beberapa key metrics untuk dashboard overview:
     * total_requests: COUNT semua request dalam periode
     * success_rate_pct: % request dengan status 'success'
     * avg_latency_ms: rata-rata total_ms untuk request sukses
     * total_cost_usd: SUM llm_cost + embedding_cost
     * active_users: COUNT DISTINCT mahasiswa_id atau session_id
   - Kembalikan: {"data": {period_days, total_requests, success_rate_pct,
                           avg_latency_ms, total_cost_usd, active_users}}

3. TRACEABILITY KE REQUIREMENTS:
   | Endpoint              | Requirement |
   |-----------------------|-------------|
   | /latency              | A1, A3      |
   | /stage-breakdown      | A2          |
   | /errors               | B1, B4      |
   | /errors/breakdown     | B2          |
   | /openai-retry         | B3          |
   | /retrieval-quality    | C1, C3, C4  |
   | /top-documents        | C2          |
   | /domain-stats         | C5          |
   | /cost                 | D2, D3      |
   | /cost/per-user        | D3          |
   | /usage/active-users   | E1, E3      |
   | /usage/new-vs-returning| E2         |
   | /usage/turns-per-session| E2        |
   | /usage/followup-rate  | E5          |
   | /admin-activity       | F3          |
   | /system/overview      | Dashboard   |
```
