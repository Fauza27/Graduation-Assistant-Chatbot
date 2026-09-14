# ADR-007: Admin Dashboard Views Security Fix

## Status
**ACCEPTED** - Implemented on September 11, 2026

## Context

During a comprehensive security audit of our Supabase database schema (using `schema_pooler.sql` dump), we discovered a critical security vulnerability where 18 admin dashboard views containing sensitive analytics data were granted `ALL` permissions to the `anon` role.

### Problem Discovery
- **Trigger**: Database schema audit using actual production dump
- **Method**: Analysis of `information_schema.table_privileges` grants
- **Scope**: 18 views with naming pattern `v_*` (admin dashboard views)
- **Risk Level**: CRITICAL - Public exposure of sensitive business data

### Affected Data Types
The exposed views contained:
- **Financial Data**: Cost per user, session, and daily operations (`v_cost_*`)
- **User Analytics**: Active user counts, retention metrics (`v_active_users_*`, `v_new_vs_returning_*`)
- **System Performance**: Error rates, latency statistics (`v_error_*`, `v_latency_*`)
- **Business Intelligence**: Retrieval quality, document usage patterns (`v_retrieval_*`, `v_top_*`)

### Attack Vectors
With `anon` role grants, anyone could access sensitive data via:
```bash
curl "https://pobgqxhneruhswxedqpf.supabase.co/rest/v1/v_cost_daily?select=*" \
  -H "apikey: [PUBLIC_ANON_KEY]"
```

## Decision

**We decided to immediately revoke ALL permissions from the `anon` role for all admin dashboard views.**

### Rationale

#### 1. **Principle of Least Privilege**
Anonymous users should only access public-facing data, never internal analytics.

#### 2. **Data Classification Alignment**
Admin dashboard data is classified as:
- **Financial**: Confidential business metrics
- **User Analytics**: Privacy-sensitive behavioral data  
- **System Performance**: Internal operational intelligence

#### 3. **Compliance Requirements**
Exposure violated:
- Data privacy best practices
- Internal security policies
- Business confidentiality requirements

#### 4. **Risk vs. Impact Assessment**
- **Risk**: HIGH - Complete exposure of business intelligence
- **Impact of Fix**: LOW - No legitimate use case for anonymous access to admin data
- **Urgency**: CRITICAL - Immediate fix required

## Implementation

### Actions Taken
```sql
-- Revoked anonymous access from all 18 admin views
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
```

### Verification
```sql
-- Confirmed 0 anonymous grants remain on admin views
SELECT table_schema, table_name, grantee, privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'public' 
  AND table_name LIKE 'v_%' 
  AND grantee = 'anon';
-- Result: 0 rows ✅
```

### Access Control Matrix (Post-Fix)

| Role | Admin Views Access | Public Data Access | Rationale |
|------|-------------------|-------------------|-----------|
| `anon` | ❌ DENIED | ✅ ALLOWED | No legitimate need for analytics access |
| `authenticated` | ✅ ALLOWED | ✅ ALLOWED | Logged-in admin users need dashboard access |
| `service_role` | ✅ ALLOWED | ✅ ALLOWED | Backend services require full operational access |

## Alternatives Considered

### Option 1: Row-Level Security (RLS)
**Rejected** - Would add complexity without additional security benefit for these specific views.

### Option 2: View Modification to Filter Data
**Rejected** - Views contain inherently sensitive aggregated data that shouldn't be public under any circumstances.

### Option 3: Create Separate Public Analytics Views  
**Rejected** - No current requirement for public analytics. Can be implemented later if needed.

### Option 4: IP Whitelisting
**Rejected** - Doesn't address the fundamental issue of inappropriate permissions.

## Consequences

### Positive Outcomes
- ✅ **Security Hardened**: Eliminated critical data exposure vulnerability
- ✅ **Compliance Achieved**: Aligned with data privacy and security policies  
- ✅ **Risk Mitigated**: Removed attack vector for business intelligence theft
- ✅ **Audit Trail**: Comprehensive documentation for future reference

### Potential Negative Impacts
- ⚠️ **Development Impact**: Developers must use authenticated requests for admin dashboard access
- ⚠️ **Testing Complexity**: Test environments must properly simulate authentication

### Mitigation Strategies
- **Development**: Updated API documentation to specify authentication requirements
- **Testing**: Ensured test suites use proper service role credentials
- **Monitoring**: Implemented alerts for future permission drift

## Monitoring & Maintenance

### Ongoing Verification
```sql
-- Weekly audit query to prevent regression
SELECT 'SECURITY_ALERT' as alert_type, 
       table_name, 
       grantee, 
       privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'public' 
  AND table_name LIKE 'v_%' 
  AND grantee = 'anon'
  AND privilege_type IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE');
```

### Future Safeguards
1. **Permission Reviews**: Quarterly access control audits
2. **Change Management**: All new views must be reviewed for appropriate permissions  
3. **Automated Monitoring**: Database permission drift detection
4. **Documentation**: This ADR serves as reference for future security decisions

## References

### Related Documents
- `backend/docs/DATABASE_SECURITY_AUDIT_2026.md` - Complete security audit report
- `backend/scripts/supabase_security_fix_admin_views.sql` - Implementation script
- `backend/docs/API_DOCUMENTATION.md` - Updated API authentication requirements

### Related ADRs
- `ADR-001` through `ADR-006` - Previous architecture decisions
- Future ADRs will reference this security baseline

---

**Decision Made By**: Kiro AI Assistant (Security Audit)  
**Date**: September 11, 2026  
**Approved By**: System Owner (via execution)  
**Review Date**: December 11, 2026  
**Next Review**: Quarterly security audit cycle