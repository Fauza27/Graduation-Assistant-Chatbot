'use client';

import { useMemo } from 'react';
import { Coins, Database, Receipt, Users2 } from 'lucide-react';
import { useMetric } from '@/lib/useMetric';
import { getCostStats, getCostPerUser } from '@/lib/monitoringApi';
import StatCard from '../StatCard';
import LineChart from '../charts/LineChart';
import { fmtThousand, fmtUsd, fmtDateShort, shortId } from '@/lib/monitoringUtils';
import type { MonTabProps } from './types';

export default function CostTab({ days }: MonTabProps) {
  const cost = useMetric(() => getCostStats(days), [days]);
  const perUser = useMetric(() => getCostPerUser(10), []);

  const sorted = useMemo(() => [...(cost.data || [])].sort((a, b) => a.day.localeCompare(b.day)), [cost.data]);

  const agg = useMemo(() => {
    const rows = cost.data || [];
    const totalLlm = rows.reduce((a, r) => a + (r.total_llm_cost_usd ?? 0), 0);
    const totalEmb = rows.reduce((a, r) => a + (r.total_embedding_cost_usd ?? 0), 0);
    const totalReq = rows.reduce((a, r) => a + r.total_requests, 0);
    const totalIn = rows.reduce((a, r) => a + (r.total_input_tokens ?? 0), 0);
    const totalOut = rows.reduce((a, r) => a + (r.total_output_tokens ?? 0), 0);
    return {
      totalLlm, totalEmb, totalReq, totalIn, totalOut,
      costPerRequest: totalReq ? (totalLlm + totalEmb) / totalReq : 0,
    };
  }, [cost.data]);

  return (
    <div>
      <div className="astat-grid">
        <StatCard label="Token Input" icon={Database} color="blue" value={fmtThousand(agg.totalIn)} note={`${days} hari terakhir`} />
        <StatCard label="Token Output" icon={Database} color="indigo" value={fmtThousand(agg.totalOut)} />
        <StatCard label="Biaya LLM" icon={Coins} color="amber" value={fmtUsd(agg.totalLlm, 3)} />
        <StatCard label="Biaya Embedding" icon={Coins} color="teal" value={fmtUsd(agg.totalEmb, 4)} />
        <StatCard label="Biaya / Request" icon={Receipt} color="purple" value={fmtUsd(agg.costPerRequest, 5)} />
      </div>

      <div className="apanel-row">
        <div className="apanel apanel-full">
          <h3>Tren Token Usage &amp; Biaya</h3>
          <p className="apanel-desc">
            Reranking berjalan lokal (CPU cross-encoder), bukan API OpenAI berbayar — jadi biaya hanya berasal dari
            LLM generation dan embedding, tidak ada &ldquo;biaya per tahap pipeline&rdquo; di luar keduanya.
          </p>
          <LineChart
            labels={sorted.map((d) => fmtDateShort(d.day))}
            series={[
              { name: 'Biaya LLM ($)', values: sorted.map((d) => d.total_llm_cost_usd ?? 0), color: 'var(--chart-amber)' },
              { name: 'Biaya Embedding ($)', values: sorted.map((d) => d.total_embedding_cost_usd ?? 0), color: 'var(--chart-blue)', dashed: true },
            ]}
            valueFormatter={(v) => `$${v.toFixed(3)}`}
          />
        </div>
      </div>

      <div className="apanel-row">
        <div className="apanel apanel-full">
          <h3>
            <Users2 style={{ width: 14, height: 14, display: 'inline', marginRight: 6, verticalAlign: -2 }} />
            Biaya per User (Top 10)
          </h3>
          <p className="apanel-desc">Total biaya (LLM + embedding) per mahasiswa, seluruh periode tersedia.</p>
          <div className="atable-scroll">
            <table className="atable">
              <thead><tr><th>Mahasiswa ID</th><th>Total Biaya</th><th>Jumlah Request</th></tr></thead>
              <tbody>
                {(perUser.data || []).map((u) => (
                  <tr key={u.mahasiswa_id}>
                    <td className="atable-mono">{shortId(u.mahasiswa_id, 18)}</td>
                    <td className="atable-mono">{fmtUsd(u.total_cost_usd, 4)}</td>
                    <td className="atable-mono">{fmtThousand(u.total_requests)}</td>
                  </tr>
                ))}
                {(!perUser.data || perUser.data.length === 0) && (
                  <tr><td colSpan={3} className="atable-empty">Belum ada data.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
