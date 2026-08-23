'use client';

import { Activity, CheckCircle2, Timer, Coins, Users, AlertOctagon } from 'lucide-react';
import { useMetric } from '@/lib/useMetric';
import { getSystemOverview, getErrorStats, getStageBreakdown } from '@/lib/monitoringApi';
import StatCard from '../StatCard';
import HBarList from '../charts/HBarList';
import StatusBanner, { type SystemStatus } from '../StatusBanner';
import { fmtThousand, fmtMs, fmtPct, fmtUsd } from '@/lib/monitoringUtils';
import { PIPELINE_STAGE_KEYS, STAGE_LABELS } from '@/lib/monitoringTypes';
import type { MonTabProps } from './types';

export default function OverviewTab({ days, queryLog, openList }: MonTabProps) {
  const overview = useMetric(() => getSystemOverview(days), [days]);
  const errorStats = useMetric(() => getErrorStats(days), [days]);
  const stageBreakdown = useMetric(() => getStageBreakdown(days), [days]);

  const latestError = errorStats.data?.[0];
  const errorRate = latestError?.error_rate_pct ?? 0;
  const successRate = overview.data?.success_rate_pct ?? 100;

  let status: SystemStatus = 'healthy';
  let statusNote = 'Semua metrik utama berada dalam batas wajar.';
  if (successRate < 90) {
    status = 'down';
    statusNote = `Success rate turun ke ${successRate.toFixed(1)}% dalam ${days} hari terakhir.`;
  } else if (successRate < 97 || errorRate > 3) {
    status = 'degraded';
    statusNote = `Error rate ${errorRate.toFixed(1)}% — di atas ambang normal, layak dipantau.`;
  }

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

  return (
    <div>
      <StatusBanner status={status} note={statusNote} />

      <div className="astat-grid">
        <StatCard label="Total Request" icon={Activity} color="purple" value={fmtThousand(overview.data?.total_requests)} note={`${days} hari terakhir`} />
        <StatCard
          label="Success Rate"
          icon={CheckCircle2}
          color="teal"
          value={fmtPct(overview.data?.success_rate_pct)}
          severity={successRate < 90 ? 'crit' : successRate < 97 ? 'warn' : 'ok'}
        />
        <StatCard label="Avg Latency" icon={Timer} color="blue" value={fmtMs(overview.data?.avg_latency_ms)} />
        <StatCard label="Total Cost" icon={Coins} color="amber" value={fmtUsd(overview.data?.total_cost_usd, 2)} />
        <StatCard label="Active Users" icon={Users} color="indigo" value={fmtThousand(overview.data?.active_users)} />
        <StatCard
          label="Error Rate"
          icon={AlertOctagon}
          color="coral"
          value={fmtPct(errorRate)}
          severity={errorRate > 5 ? 'crit' : errorRate > 2 ? 'warn' : 'ok'}
        />
      </div>

      <div className="apanel-row">
        <div className="apanel apanel-full">
          <h3>Breakdown Latency per Tahap Pipeline (E2E)</h3>
          <p className="apanel-desc">Klik salah satu tahap untuk melihat request paling lambat di tahap itu.</p>
          {pipelineItems.length > 0 ? (
            <HBarList items={pipelineItems} numbered />
          ) : (
            <p style={{ fontSize: 12.5, color: 'var(--gray-400)' }}>Memuat…</p>
          )}
        </div>
      </div>
    </div>
  );
}
