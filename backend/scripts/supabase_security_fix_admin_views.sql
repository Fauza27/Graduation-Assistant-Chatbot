-- =====================================================
-- SECURITY FIX: Revoke Anonymous Access from Admin Views
-- =====================================================
-- 
-- Issue: 18 admin dashboard views currently have GRANT ALL TO anon
-- Risk: Sensitive analytics data (costs, errors, user stats) exposed publicly
-- 
-- Views affected:
-- - v_active_users_daily, v_active_users_monthly
-- - v_admin_activity_daily  
-- - v_avg_turns_per_session_daily
-- - v_cost_daily, v_cost_per_session, v_cost_per_user
-- - v_domain_stats_daily
-- - v_error_breakdown_daily, v_error_stats_daily
-- - v_followup_rate_daily
-- - v_latency_stats_hourly
-- - v_session_first_seen, v_new_vs_returning_daily
-- - v_openai_retry_stats_daily
-- - v_retrieval_quality_daily
-- - v_stage_breakdown_daily
-- - v_top_retrieved_documents
--
-- Date: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
-- =====================================================

-- Revoke anonymous access from all admin dashboard views
REVOKE ALL ON TABLE public.v_active_users_daily FROM anon;
REVOKE ALL ON TABLE public.v_active_users_monthly FROM anon;
REVOKE ALL ON TABLE public.v_admin_activity_daily FROM anon;
REVOKE ALL ON TABLE public.v_avg_turns_per_session_daily FROM anon;
REVOKE ALL ON TABLE public.v_cost_daily FROM anon;
REVOKE ALL ON TABLE public.v_cost_per_session FROM anon;
REVOKE ALL ON TABLE public.v_cost_per_user FROM anon;
REVOKE ALL ON TABLE public.v_domain_stats_daily FROM anon;
REVOKE ALL ON TABLE public.v_error_breakdown_daily FROM anon;
REVOKE ALL ON TABLE public.v_error_stats_daily FROM anon;
REVOKE ALL ON TABLE public.v_followup_rate_daily FROM anon;
REVOKE ALL ON TABLE public.v_latency_stats_hourly FROM anon;
REVOKE ALL ON TABLE public.v_session_first_seen FROM anon;
REVOKE ALL ON TABLE public.v_new_vs_returning_daily FROM anon;
REVOKE ALL ON TABLE public.v_openai_retry_stats_daily FROM anon;
REVOKE ALL ON TABLE public.v_retrieval_quality_daily FROM anon;
REVOKE ALL ON TABLE public.v_stage_breakdown_daily FROM anon;
REVOKE ALL ON TABLE public.v_top_retrieved_documents FROM anon;

-- Verify no anonymous access remains (should return 0 rows)
SELECT schemaname, tablename, grantee, privilege_type
FROM information_schema.table_privileges 
WHERE schemaname = 'public' 
  AND tablename LIKE 'v_%' 
  AND grantee = 'anon'
  AND privilege_type IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE');

-- Show what access authenticated users still have (should show service_role and authenticated)
SELECT schemaname, tablename, grantee, privilege_type
FROM information_schema.table_privileges 
WHERE schemaname = 'public' 
  AND tablename LIKE 'v_%' 
  AND grantee IN ('authenticated', 'service_role')
  AND privilege_type IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE')
ORDER BY tablename, grantee;

-- Log the security fix
INSERT INTO public.admin_logs (action_type, description, performed_by, performed_at) 
VALUES (
  'SECURITY_FIX', 
  'Revoked anonymous access from 18 admin dashboard views to prevent data exposure',
  'system_maintenance',
  NOW()
) 
ON CONFLICT DO NOTHING; -- In case admin_logs table doesn't exist