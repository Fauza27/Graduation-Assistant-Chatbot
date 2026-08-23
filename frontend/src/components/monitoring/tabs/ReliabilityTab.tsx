'use client';

import { useMemo } from 'react';
import { AlertOctagon, Clock3, RefreshCcw, ShieldAlert } from 'lucide-react';
import { useMetric } from '@/lib/useMetric';
import { getErrorStats, getErrorBreakdown, getOpenAIRetryStats } from '@/lib/monitoringApi';
import StatCard from '../StatCard';
import DonutChart from '../charts/DonutChart';
import LineChart from '../charts/LineChart';
import {
  deriveErrorDetail, formatErrorSource, fmtDateShort, fmtDateTime, fmtPct, shortId,
} from '@/lib/monitoringUtils';
import type { MonTabProps } from './types';

const SOURCE_COLORS: Record<string, string> = {
  openai: 'var(--chart-purple)',
  supabase: 'var(--chart-coral)',
  validation: 'var(--chart-blue)',
  rate_limit: 'var(--chart-amber)',
  unknown: 'var(--gray-400)',
};

export default function ReliabilityTab({ days, queryLog, openList, openDetail }: MonTabProps) {
  const errorStats = useMetric(() => getErrorStats(days), [days]);
  const errorBreakdown = useMetric(() => getErrorBreakdown(days), [days]);
  const retryStats = useMetric(() => getOpenAIRetryStats(days), [days]);

  const sorted = useMemo(() => [...(errorStats.data || [])].sort((a, b) => a.day.localeCompare(b.day)), [errorStats.data]);
  const latest = sorted[sorted.length - 1];
  const avgRetryPct = retryStats.data?.length
    ? retryStats.data.reduce((a, r) => a + r.pct_requests_with_retry, 0) / retryStats.data.length
    : 0;

  const errorRows = useMemo(() => queryLog.filter((r) => r.status === 'error'), [queryLog]);
  const timeoutCount = errorRows.filter((r) => (r.error_type || '').toLowerCase().includes('timeout')).length;
  const timeoutRate = queryLog.length ? (timeoutCount / queryLog.length) * 100 : 0;

  const breakdownAgg = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of errorBreakdown.data || []) {
      map.set(r.error_source, (map.get(r.error_source) || 0) + r.error_count);
    }
    const total = [...map.values()].reduce((a, b) => a + b, 0) || 1;
    return [...map.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([source, value]) => ({
        label: formatErrorSource(source as never),
        value,
        pct: Math.round((value / total) * 1000) / 10,
        color: SOURCE_COLORS[source] || 'var(--gray-400)',
      }));
  }, [errorBreakdown.data]);

  const recentErrors = [...errorRows]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 6);

  return (
    <div>
      <div className="astat-grid">
        <StatCard
          label="Error Rate"
          icon={AlertOctagon}
          color="coral"
          value={fmtPct(latest?.error_rate_pct)}
          severity={(latest?.error_rate_pct ?? 0) > 5 ? 'crit' : (latest?.error_rate_pct ?? 0) > 2 ? 'warn' : 'ok'}
        />
        <StatCard label="Timeout Rate" icon={Clock3} color="amber" value={fmtPct(timeoutRate)} note="dari total request" />
        <StatCard label="Retry Rate ke OpenAI" icon={RefreshCcw} color="blue" value={fmtPct(avgRetryPct)} note="request butuh ≥1 retry" />
        <StatCard
          label="Quota-Rejection Rate"
          icon={ShieldAlert}
          color="indigo"
          value={fmtPct(latest?.quota_rejection_rate_pct)}
          note="dari limit harian"
        />
      </div>

      <div className="apanel-row">
        <div className="apanel">
          <h3>Tren Error &amp; Quota Rejection</h3>
          <p className="apanel-desc">Persentase harian, {days} hari terakhir.</p>
          <LineChart
            labels={sorted.map((d) => fmtDateShort(d.day))}
            series={[
              { name: 'Error Rate', values: sorted.map((d) => d.error_rate_pct), color: 'var(--chart-coral)' },
              { name: 'Quota Rejected', values: sorted.map((d) => d.quota_rejection_rate_pct), color: 'var(--chart-amber)', dashed: true },
            ]}
            valueFormatter={(v) => `${v.toFixed(1)}%`}
          />
        </div>
        <div className="apanel">
          <h3>Breakdown Error by Source</h3>
          <p className="apanel-desc">{days} hari terakhir.</p>
          {breakdownAgg.length > 0 ? (
            <DonutChart data={breakdownAgg} unitLabel="error" totalLabel="Total Error" />
          ) : (
            <p style={{ fontSize: 12.5, color: 'var(--gray-400)' }}>Belum ada error tercatat.</p>
          )}
        </div>
      </div>

      <div className="apanel-row">
        <div className="apanel apanel-full">
          <h3>Log Error Terbaru</h3>
          <p className="apanel-desc">Session &amp; user yang mengalami error — klik untuk detail lengkap.</p>
          <div className="atable-scroll">
            <table className="atable">
              <thead>
                <tr>
                  <th>Waktu</th>
                  <th>Session / User</th>
                  <th>Pertanyaan</th>
                  <th>Sumber Error</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {recentErrors.length === 0 && (
                  <tr><td colSpan={5} className="atable-empty">Tidak ada error pada periode ini.</td></tr>
                )}
                {recentErrors.map((r) => (
                  <tr key={r.request_id} className="atable-row-clickable" onClick={() => openDetail(r.request_id)}>
                    <td className="atable-mono">{fmtDateTime(r.created_at)}</td>
                    <td>
                      <div className="atable-user">{r.username || shortId(r.session_id)}</div>
                      <div className="atable-sub">{shortId(r.session_id)}</div>
                    </td>
                    <td className="atable-question" title={r.question || ''}>{r.question || '—'}</td>
                    <td><span className="status-badge status-danger">{formatErrorSource(r.error_source)}</span></td>
                    <td className="atable-sub" style={{ maxWidth: 220 }}>{deriveErrorDetail(r.error_source, r.error_type)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            className="atable-more-link"
            onClick={() => openList({ title: 'Semua Error — Session & Akun', subtitle: `${days} hari terakhir`, rows: errorRows })}
          >
            Lihat Semua Error ({errorRows.length}) →
          </button>
        </div>
      </div>
    </div>
  );
}
