'use client';

import { useMemo } from 'react';
import { Users, Repeat, MessagesSquare, Gauge } from 'lucide-react';
import { useMetric } from '@/lib/useMetric';
import { getActiveUsers, getNewVsReturning, getTurnsPerSession, getFollowupRate } from '@/lib/monitoringApi';
import StatCard from '../StatCard';
import DonutChart from '../charts/DonutChart';
import LineChart from '../charts/LineChart';
import { fmtThousand, fmtPct, fmtDateShort, formatChannel } from '@/lib/monitoringUtils';
import type { MonTabProps } from './types';

export default function UsageTab({ days, queryLog, openList }: MonTabProps) {
  const dau = useMetric(() => getActiveUsers('daily', days), [days]);
  const mau = useMetric(() => getActiveUsers('monthly', 30), []);
  const newVsReturn = useMetric(() => getNewVsReturning(days), [days]);
  const turns = useMetric(() => getTurnsPerSession(days), [days]);
  const followup = useMetric(() => getFollowupRate(days), [days]);

  const dauTotal = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of dau.data || []) map.set(r.day || '', (map.get(r.day || '') || 0) + r.active_users);
    const days2 = [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
    return days2[days2.length - 1]?.[1] ?? 0;
  }, [dau.data]);
  const mauTotal = useMemo(() => (mau.data || []).reduce((a, r) => a + r.active_users, 0), [mau.data]);

  const dauSeries = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of dau.data || []) map.set(r.day || '', (map.get(r.day || '') || 0) + r.active_users);
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [dau.data]);

  const channelSplit = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of queryLog) map.set(r.channel, (map.get(r.channel) || 0) + 1);
    const total = queryLog.length || 1;
    return [...map.entries()].map(([ch, v]) => ({
      label: formatChannel(ch),
      value: v,
      pct: Math.round((v / total) * 1000) / 10,
      color: ch === 'website' ? 'var(--chart-purple)' : ch === 'telegram' ? 'var(--chart-blue)' : 'var(--gray-400)',
    }));
  }, [queryLog]);

  const nvr = newVsReturn.data?.reduce(
    (a, r) => ({ n: a.n + r.requests_from_new_sessions, r: a.r + r.requests_from_returning_sessions }),
    { n: 0, r: 0 }
  ) || { n: 0, r: 0 };
  const nvrTotal = nvr.n + nvr.r || 1;
  const nvrData = [
    { label: 'Sesi Baru', value: nvr.n, pct: Math.round((nvr.n / nvrTotal) * 1000) / 10, color: 'var(--chart-purple)' },
    { label: 'Sesi Lanjutan', value: nvr.r, pct: Math.round((nvr.r / nvrTotal) * 1000) / 10, color: 'var(--chart-blue)' },
  ];

  const avgTurns = turns.data?.length ? turns.data.reduce((a, r) => a + r.avg_turns_per_session, 0) / turns.data.length : 0;
  const avgFollowup = followup.data?.length ? followup.data.reduce((a, r) => a + r.followup_rate_pct, 0) / followup.data.length : 0;

  const quotaRejectedRows = useMemo(() => queryLog.filter((r) => r.status === 'quota_rejected'), [queryLog]);
  const quotaHitPct = queryLog.length ? (quotaRejectedRows.length / queryLog.length) * 100 : 0;

  return (
    <div>
      <div className="astat-grid">
        <StatCard label="Active Users (Harian)" icon={Users} color="purple" value={fmtThousand(dauTotal)} />
        <StatCard label="Active Users (30 Hari)" icon={Users} color="indigo" value={fmtThousand(mauTotal)} />
        <StatCard label="Avg Turn / Sesi" icon={MessagesSquare} color="blue" value={avgTurns.toFixed(1)} />
        <StatCard
          label="% Kena Limit Kuota"
          icon={Gauge}
          color="amber"
          value={fmtPct(quotaHitPct)}
          severity={quotaHitPct > 15 ? 'warn' : 'ok'}
          onClick={() => openList({ title: 'Request yang Kena Limit Kuota Harian', subtitle: `${days} hari terakhir`, rows: quotaRejectedRows })}
        />
        <StatCard label="Follow-up Rate" icon={Repeat} color="teal" value={fmtPct(avgFollowup)} note="proxy dari rewrite_method" />
      </div>

      <div className="apanel-row">
        <div className="apanel">
          <h3>Tren Active Users Harian</h3>
          <LineChart
            labels={dauSeries.map(([d]) => fmtDateShort(d))}
            series={[{ name: 'Active Users', values: dauSeries.map(([, v]) => v), color: 'var(--chart-purple)' }]}
            area
          />
        </div>
        <div className="apanel">
          <h3>Distribusi Channel</h3>
          {channelSplit.length > 0 ? <DonutChart data={channelSplit} totalLabel="Total Request" /> : <p style={{ fontSize: 12.5, color: 'var(--gray-400)' }}>Belum ada data.</p>}
        </div>
      </div>

      <div className="apanel-row">
        <div className="apanel">
          <h3>Sesi Baru vs Lanjutan</h3>
          <p className="apanel-desc">Dihitung dari jumlah turn, bukan jumlah sesi unik.</p>
          <DonutChart data={nvrData} unitLabel="turn" totalLabel="Total Turn" />
        </div>
        <div className="apanel">
          <h3>Tren Follow-up Rate</h3>
          <p className="apanel-desc">Sinyal proxy — deteksi query lanjutan lewat query reformulation.</p>
          <LineChart
            labels={(followup.data || []).slice().reverse().map((d) => fmtDateShort(d.day))}
            series={[{ name: 'Follow-up', values: (followup.data || []).slice().reverse().map((d) => d.followup_rate_pct), color: 'var(--chart-teal, #0D9488)' }]}
            valueFormatter={(v) => `${v.toFixed(1)}%`}
          />
        </div>
      </div>
    </div>
  );
}
