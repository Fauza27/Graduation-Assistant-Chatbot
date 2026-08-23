'use client';

import { useMemo } from 'react';
import { Server, Database, Cpu, Sparkles, Cable, HardDrive, Info } from 'lucide-react';
import { useMetric } from '@/lib/useMetric';
import { getSystemHealth, getAdminActivity } from '@/lib/monitoringApi';
import StatCard from '../StatCard';
import { fmtThousand, fmtPct } from '@/lib/monitoringUtils';
import type { MonTabProps } from './types';

interface CompRow {
  name: string;
  icon: typeof Server;
  status: 'ok' | 'warn' | 'down';
  note: string;
}

export default function HealthTab({ queryLog }: MonTabProps) {
  const system = useMetric(() => getSystemHealth(), []);
  const adminActivity = useMetric(() => getAdminActivity(30), []);

  const active = (system.data?.session_stats?.active_sessions as number) ?? (system.data?.session_stats?.total_sessions as number) ?? 0;
  const max = system.data?.max_active_sessions ?? 1000;
  const util = system.data?.utilization_pct ?? 0;

  // Kesehatan reranker: bandingkan rata-rata 20 request TERBARU vs rata-rata
  // keseluruhan periode. Dibangun dari data stage_reranking_ms yang memang
  // sudah dikumpulkan real-time — tidak butuh health-check sintetis baru.
  const rerankHealth = useMemo(() => {
    const withRerank = queryLog.filter((r) => r.stage_reranking_ms != null);
    if (withRerank.length === 0) return { status: 'ok' as const, note: 'Belum ada data.' };
    const overallAvg = withRerank.reduce((a, r) => a + (r.stage_reranking_ms ?? 0), 0) / withRerank.length;
    const recent = withRerank.slice(0, 20);
    const recentAvg = recent.reduce((a, r) => a + (r.stage_reranking_ms ?? 0), 0) / recent.length;
    const ratio = overallAvg > 0 ? recentAvg / overallAvg : 1;
    if (ratio > 2) return { status: 'warn' as const, note: `Rata-rata ${Math.round(recentAvg)}ms, biasanya ~${Math.round(overallAvg)}ms` };
    return { status: 'ok' as const, note: `Rata-rata ${Math.round(recentAvg)}ms — normal` };
  }, [queryLog]);

  const openaiErrRate = useMemo(() => {
    const recent = queryLog.slice(0, 50);
    const errs = recent.filter((r) => r.error_source === 'openai').length;
    return recent.length ? (errs / recent.length) * 100 : 0;
  }, [queryLog]);
  const supabaseErrRate = useMemo(() => {
    const recent = queryLog.slice(0, 50);
    const errs = recent.filter((r) => r.error_source === 'supabase').length;
    return recent.length ? (errs / recent.length) * 100 : 0;
  }, [queryLog]);

  const components: CompRow[] = [
    { name: 'API Server', icon: Server, status: 'ok', note: 'Merespons normal' },
    {
      name: 'Database (Supabase)', icon: Database,
      status: supabaseErrRate > 10 ? 'down' : supabaseErrRate > 3 ? 'warn' : 'ok',
      note: supabaseErrRate > 0 ? `${supabaseErrRate.toFixed(0)}% error dari 50 request terakhir` : 'Normal',
    },
    {
      name: 'LLM Provider (OpenAI)', icon: Sparkles,
      status: openaiErrRate > 10 ? 'down' : openaiErrRate > 3 ? 'warn' : 'ok',
      note: openaiErrRate > 0 ? `${openaiErrRate.toFixed(0)}% error dari 50 request terakhir` : 'Normal',
    },
    { name: 'Embedding Provider (OpenAI)', icon: Cable, status: 'ok', note: 'Sama dengan LLM provider' },
    { name: 'Reranker Service (lokal)', icon: Cpu, status: rerankHealth.status, note: rerankHealth.note },
    { name: 'Session Store', icon: HardDrive, status: util > 90 ? 'warn' : 'ok', note: `${fmtThousand(active)} / ${fmtThousand(max)} sesi aktif` },
  ];

  const activityTotal = (adminActivity.data || []).reduce(
    (a, r) => ({ edits: a.edits + r.total_edits, reembeds: a.reembeds + r.successful_reembeds }),
    { edits: 0, reembeds: 0 }
  );

  return (
    <div>
      <div className="apanel-row">
        <div className="apanel">
          <h3>Kapasitas Session</h3>
          <div className="gauge-wrap">
            <div className="gauge-value">{fmtPct(util)}</div>
            <div className="gauge-track">
              <div
                className="gauge-fill"
                style={{ width: `${Math.min(util, 100)}%`, background: util > 90 ? 'var(--status-danger-dot)' : util > 70 ? 'var(--status-warning-dot)' : 'var(--status-success-dot)' }}
              />
            </div>
            <p style={{ fontSize: 12, color: 'var(--gray-400)', marginTop: 4 }}>
              {fmtThousand(active)} dari {fmtThousand(max)} sesi (MAX_ACTIVE_SESSIONS)
            </p>
          </div>
          <div className="empty-state" style={{ padding: '14px 10px', marginTop: 8 }}>
            <Info style={{ width: 18, height: 18, color: 'var(--gray-400)' }} />
            <p style={{ margin: '4px 0 0', fontSize: 11.5 }}>
              Efektivitas idle cleanup (jumlah &amp; rata-rata idle sebelum dibersihkan) belum tersedia — perlu tabel log
              cleanup terpisah yang belum diimplementasikan.
            </p>
          </div>
        </div>

        <div className="apanel">
          <h3>Uptime</h3>
          <div className="empty-state" style={{ padding: '20px 14px' }}>
            <Info style={{ width: 20, height: 20, color: 'var(--gray-400)' }} />
            <h3 style={{ fontSize: 13 }}>Belum tersedia</h3>
            <p>
              Histori uptime perlu monitoring eksternal (mis. UptimeRobot) atau job self-ping terjadwal — belum ada di
              backend saat ini. Endpoint <code>/health/liveness</code> sudah siap dipakai kalau mau dihubungkan.
            </p>
          </div>
        </div>
      </div>

      <div className="apanel-row">
        <div className="apanel apanel-full">
          <h3>Status Komponen</h3>
          <div className="health-comp-list">
            {components.map((c) => (
              <div className="health-comp-row" key={c.name}>
                <div className="health-comp-left">
                  <c.icon style={{ width: 16, height: 16, color: 'var(--gray-500)' }} />
                  <div>
                    <div className="health-comp-name">{c.name}</div>
                    <div className="health-comp-note">{c.note}</div>
                  </div>
                </div>
                <span className={`health-dot ${c.status}`} />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="apanel-row">
        <div className="apanel apanel-full">
          <div className="astat-grid" style={{ marginBottom: 0 }}>
            <StatCard label="Total Edit Chunk" icon={Server} color="indigo" value={fmtThousand(activityTotal.edits)} note="30 hari terakhir" />
            <StatCard label="Re-embed Berhasil" icon={Database} color="teal" value={fmtThousand(activityTotal.reembeds)} note="30 hari terakhir" />
          </div>
        </div>
      </div>
    </div>
  );
}
