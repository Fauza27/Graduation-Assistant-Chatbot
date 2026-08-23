'use client';

import { useMemo } from 'react';
import { Gauge, TrendingUp, Zap, Activity } from 'lucide-react';
import { useMetric } from '@/lib/useMetric';
import { getLatencyStats, getStageBreakdown } from '@/lib/monitoringApi';
import StatCard from '../StatCard';
import HBarList from '../charts/HBarList';
import LineChart from '../charts/LineChart';
import {
  deriveDisplayStatus, STATUS_BADGE_CLASS, STATUS_LABEL,
  fmtMs, fmtThousand, fmtDateShort, fmtDateTime, shortId,
} from '@/lib/monitoringUtils';
import { PIPELINE_STAGE_KEYS, STAGE_LABELS } from '@/lib/monitoringTypes';
import type { MonTabProps } from './types';

function groupByDay(rows: { bucket: string; p50_ms: number | null; p95_ms: number | null; p99_ms: number | null; total_requests: number }[]) {
  const map = new Map<string, { p50: number[]; p95: number[]; p99: number[]; total: number }>();
  for (const r of rows) {
    const day = r.bucket.slice(0, 10);
    const g = map.get(day) || { p50: [], p95: [], p99: [], total: 0 };
    if (r.p50_ms != null) g.p50.push(r.p50_ms);
    if (r.p95_ms != null) g.p95.push(r.p95_ms);
    if (r.p99_ms != null) g.p99.push(r.p99_ms);
    g.total += r.total_requests;
    map.set(day, g);
  }
  const avg = (a: number[]) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0);
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, g]) => ({ day, p50: avg(g.p50), p95: avg(g.p95), p99: avg(g.p99), total: g.total }));
}

export default function PerformanceTab({ days, queryLog, openList, openDetail }: MonTabProps) {
  const latency = useMetric(() => getLatencyStats(days), [days]);
  const stageBreakdown = useMetric(() => getStageBreakdown(days), [days]);

  const daily = useMemo(() => groupByDay(latency.data || []), [latency.data]);
  const totalReq = daily.reduce((a, d) => a + d.total, 0);
  const avgP50 = daily.length ? daily.reduce((a, d) => a + d.p50, 0) / daily.length : 0;
  const avgP95 = daily.length ? daily.reduce((a, d) => a + d.p95, 0) / daily.length : 0;
  const avgP99 = daily.length ? daily.reduce((a, d) => a + d.p99, 0) / daily.length : 0;
  const rpm = totalReq / (days * 24 * 60);
  const rps = totalReq / (days * 24 * 3600);

  const stageRow = stageBreakdown.data?.[0];
  const pipelineItems = stageRow
    ? PIPELINE_STAGE_KEYS.map((key) => {
        const avgKey = `avg_${key.replace('stage_', '')}` as keyof typeof stageRow;
        const val = (stageRow[avgKey] as number | null) ?? 0;
        return {
          label: STAGE_LABELS[key],
          value: val,
          valueLabel: fmtMs(val),
          onClick: () =>
            openList({
              title: `Latency Tertinggi — ${STAGE_LABELS[key]}`,
              subtitle: `${days} hari terakhir, terurut dari yang paling lambat`,
              rows: queryLog,
              highlightStage: key,
            }),
        };
      })
    : [];

  const recentRows = [...queryLog]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 8);

  return (
    <div>
      <div className="astat-grid">
        <StatCard label="Rata-rata Latency (P50)" icon={Gauge} color="purple" value={fmtMs(avgP50)} />
        <StatCard label="P95 Latency" icon={TrendingUp} color="amber" value={fmtMs(avgP95)} severity={avgP95 > 6000 ? 'warn' : 'ok'} />
        <StatCard label="P99 Latency" icon={TrendingUp} color="coral" value={fmtMs(avgP99)} severity={avgP99 > 10000 ? 'crit' : 'ok'} />
        <StatCard label="Throughput" icon={Zap} color="blue" value={`${rpm.toFixed(2)} RPM`} note={`${rps.toFixed(3)} RPS`} />
        <StatCard label="Total Request" icon={Activity} color="indigo" value={fmtThousand(totalReq)} note={`${days} hari terakhir`} />
      </div>

      <div className="apanel-row">
        <div className="apanel apanel-full">
          <h3>Tren Latency (P50 / P95 / P99)</h3>
          <p className="apanel-desc">Rata-rata harian, {days} hari terakhir.</p>
          <LineChart
            labels={daily.map((d) => fmtDateShort(d.day))}
            series={[
              { name: 'P50', values: daily.map((d) => d.p50), color: 'var(--chart-purple)' },
              { name: 'P95', values: daily.map((d) => d.p95), color: 'var(--chart-amber)' },
              { name: 'P99', values: daily.map((d) => d.p99), color: 'var(--chart-coral)', dashed: true },
            ]}
            valueFormatter={(v) => `${Math.round(v)}ms`}
          />
        </div>
      </div>

      <div className="apanel-row">
        <div className="apanel apanel-full">
          <h3>Breakdown Latency per Tahap Pipeline (E2E)</h3>
          <p className="apanel-desc">Klik tahap untuk melihat request paling lambat di tahap tersebut, lengkap dengan session &amp; pertanyaan.</p>
          {pipelineItems.length > 0 ? <HBarList items={pipelineItems} numbered /> : <p style={{ fontSize: 12.5, color: 'var(--gray-400)' }}>Memuat…</p>}
        </div>
      </div>

      <div className="apanel-row">
        <div className="apanel apanel-full">
          <h3>Histori Request Terbaru</h3>
          <p className="apanel-desc">Klik baris untuk melihat detail lengkap request.</p>
          <div className="atable-scroll">
            <table className="atable">
              <thead>
                <tr>
                  <th>Waktu</th>
                  <th>Session</th>
                  <th>Pertanyaan</th>
                  <th>Channel</th>
                  <th>Latency</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {recentRows.map((r) => {
                  const dstatus = deriveDisplayStatus(r);
                  return (
                    <tr key={r.request_id} className="atable-row-clickable" onClick={() => openDetail(r.request_id)}>
                      <td className="atable-mono">{fmtDateTime(r.created_at)}</td>
                      <td className="atable-mono">{shortId(r.session_id)}</td>
                      <td className="atable-question" title={r.question || ''}>{r.question || '—'}</td>
                      <td>{r.channel}</td>
                      <td className="atable-mono">{fmtMs(r.total_ms)}</td>
                      <td>
                        <span className={`status-badge ${STATUS_BADGE_CLASS[dstatus]}`}>{STATUS_LABEL[dstatus]}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <button
            className="atable-more-link"
            onClick={() =>
              openList({ title: 'Histori Request Lengkap', subtitle: `${days} hari terakhir`, rows: queryLog })
            }
          >
            Lihat Semua ({queryLog.length}) →
          </button>
        </div>
      </div>
    </div>
  );
}
