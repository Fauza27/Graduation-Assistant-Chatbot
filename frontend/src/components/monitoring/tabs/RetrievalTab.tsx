'use client';

import { useMemo } from 'react';
import { FileX2, Layers3, Target } from 'lucide-react';
import { useMetric } from '@/lib/useMetric';
import { getRetrievalQuality, getTopDocuments, getDomainStats } from '@/lib/monitoringApi';
import StatCard from '../StatCard';
import VBarChart from '../charts/VBarChart';
import { fmtPct, fmtThousand, formatDomain, shortId } from '@/lib/monitoringUtils';
import type { MonTabProps } from './types';

const SCORE_BUCKETS = [
  { label: '0.0–0.2', low: 0, high: 0.2 },
  { label: '0.2–0.4', low: 0.2, high: 0.4 },
  { label: '0.4–0.6', low: 0.4, high: 0.6 },
  { label: '0.6–0.8', low: 0.6, high: 0.8 },
  { label: '0.8–1.0', low: 0.8, high: 1.01 },
];

export default function RetrievalTab({ days, queryLog, openList }: MonTabProps) {
  const quality = useMetric(() => getRetrievalQuality(days), [days]);
  const topDocs = useMetric(() => getTopDocuments(15), []);
  const domainStats = useMetric(() => getDomainStats(days), [days]);

  const agg = useMemo(() => {
    const rows = quality.data || [];
    const totalQueries = rows.reduce((a, r) => a + r.total_queries, 0);
    const noDocCount = rows.reduce((a, r) => a + r.no_relevant_doc_count, 0);
    const avgDocs = rows.length ? rows.reduce((a, r) => a + (r.avg_docs_after_rerank ?? 0), 0) / rows.length : 0;
    return { totalQueries, noDocCount, noDocPct: totalQueries ? (noDocCount / totalQueries) * 100 : 0, avgDocs };
  }, [quality.data]);

  const scoreDist = useMemo(() => {
    const withScore = queryLog.filter((r) => r.top_cross_encoder_score != null);
    return SCORE_BUCKETS.map((b) => ({
      label: b.label,
      value: withScore.filter((r) => (r.top_cross_encoder_score as number) >= b.low && (r.top_cross_encoder_score as number) < b.high).length,
      color: 'var(--chart-purple)',
      unit: 'pertanyaan',
      onClick: () =>
        openList({
          title: `Skor Cross-Encoder ${b.label}`,
          subtitle: `Pertanyaan dengan skor top di rentang ${b.label}`,
          rows: withScore.filter((r) => (r.top_cross_encoder_score as number) >= b.low && (r.top_cross_encoder_score as number) < b.high),
        }),
    }));
  }, [queryLog, openList]);

  const domainAgg = useMemo(() => {
    const map = new Map<string, { total: number; failed: number }>();
    for (const r of domainStats.data || []) {
      const g = map.get(r.domain) || { total: 0, failed: 0 };
      g.total += r.total_queries;
      g.failed += r.failed_retrieval_count;
      map.set(r.domain, g);
    }
    return [...map.entries()].sort((a, b) => b[1].total - a[1].total);
  }, [domainStats.data]);

  const noRelevantRows = useMemo(() => queryLog.filter((r) => r.is_no_relevant_doc), [queryLog]);

  return (
    <div>
      <div className="astat-grid">
        <StatCard
          label="Query Tanpa Dokumen Relevan"
          icon={FileX2}
          color="coral"
          value={fmtPct(agg.noDocPct)}
          note={`${fmtThousand(agg.noDocCount)} pertanyaan`}
          severity={agg.noDocPct > 20 ? 'crit' : agg.noDocPct > 10 ? 'warn' : 'ok'}
          onClick={() => openList({ title: 'Pertanyaan Tanpa Dokumen Relevan', subtitle: `${days} hari terakhir`, rows: noRelevantRows })}
        />
        <StatCard label="Rata-rata Chunk Lolos Rerank" icon={Layers3} color="teal" value={agg.avgDocs.toFixed(1)} />
      </div>

      <div className="apanel-row">
        <div className="apanel">
          <h3>Distribusi Skor Cross-Encoder</h3>
          <p className="apanel-desc">Klik bar untuk melihat daftar pertanyaannya.</p>
          <VBarChart items={scoreDist} />
        </div>
        <div className="apanel">
          <h3>Dokumen Paling Sering Diambil</h3>
          <p className="apanel-desc">Berdasarkan parent_id — belum ada nama file di skema saat ini.</p>
          <div className="atable-scroll">
            <table className="atable atable-compact">
              <thead><tr><th>Parent ID</th><th>Jumlah</th></tr></thead>
              <tbody>
                {(topDocs.data || []).slice(0, 8).map((d) => (
                  <tr key={d.parent_id}>
                    <td className="atable-mono" title={d.parent_id}>{shortId(d.parent_id, 22)}</td>
                    <td className="atable-mono">{fmtThousand(d.times_retrieved)}</td>
                  </tr>
                ))}
                {(!topDocs.data || topDocs.data.length === 0) && (
                  <tr><td colSpan={2} className="atable-empty">Belum ada data.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="apanel-row">
        <div className="apanel apanel-full">
          <h3>
            <Target style={{ width: 14, height: 14, display: 'inline', marginRight: 6, verticalAlign: -2 }} />
            Breakdown Query per Domain
          </h3>
          <p className="apanel-desc">Klik baris untuk melihat daftar pertanyaan di domain tersebut.</p>
          <div className="atable-scroll">
            <table className="atable">
              <thead>
                <tr><th>Domain</th><th>Jumlah Query</th><th>Gagal Retrieval</th><th>% Gagal</th></tr>
              </thead>
              <tbody>
                {domainAgg.map(([domain, g]) => (
                  <tr
                    key={domain}
                    className="atable-row-clickable"
                    onClick={() =>
                      openList({
                        title: `Pertanyaan Domain ${formatDomain(domain as never)}`,
                        subtitle: `${days} hari terakhir`,
                        rows: queryLog.filter((r) => (r.domain_detected || 'UNKNOWN') === domain),
                      })
                    }
                  >
                    <td>{formatDomain(domain as never)}</td>
                    <td className="atable-mono">{fmtThousand(g.total)}</td>
                    <td className="atable-mono">{fmtThousand(g.failed)}</td>
                    <td className="atable-mono">{fmtPct(g.total ? (g.failed / g.total) * 100 : 0)}</td>
                  </tr>
                ))}
                {domainAgg.length === 0 && <tr><td colSpan={4} className="atable-empty">Belum ada data.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
