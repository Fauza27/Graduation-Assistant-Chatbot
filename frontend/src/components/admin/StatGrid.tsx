'use client';

import { FileText, Layers, Box, Clock } from 'lucide-react';
import { SummaryStats } from '@/lib/adminTypes';

interface StatGridProps {
  summary?: SummaryStats;
}

export default function StatGrid({ summary }: StatGridProps) {
  if (!summary) return null;

  // Format date to match mockup: "10 Agu 2026 10.55" with "WIB" as sub
  const formatDate = (isoString: string) => {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return { date: 'Belum pernah', sub: '' };
    const dateStr = d.toLocaleDateString('id-ID', {
      day: 'numeric', month: 'short', year: 'numeric',
    });
    const timeStr = d.toLocaleTimeString('id-ID', {
      hour: '2-digit', minute: '2-digit', hour12: false
    }).replace(':', '.');
    return { date: `${dateStr} ${timeStr}`, sub: 'WIB' };
  };

  const lastUpdated = formatDate(summary.last_updated_at);

  return (
    <div className="stat-grid" id="statGrid">
      <div className="card stat-card">
        <div className="stat-icon">
          <FileText strokeWidth={2} />
        </div>
        <div className="stat-meta">
          <div className="stat-label">Total Dokumen</div>
          <div className="stat-value">{summary.total_documents}</div>
          <div className="stat-sub">dokumen</div>
        </div>
      </div>
      <div className="card stat-card">
        <div className="stat-icon">
          <Layers strokeWidth={2} />
        </div>
        <div className="stat-meta">
          <div className="stat-label">Total Parent Chunk</div>
          <div className="stat-value">{summary.total_parents}</div>
          <div className="stat-sub">parent</div>
        </div>
      </div>
      <div className="card stat-card">
        <div className="stat-icon">
          <Box strokeWidth={2} />
        </div>
        <div className="stat-meta">
          <div className="stat-label">Total Child Chunk</div>
          <div className="stat-value">{summary.total_children}</div>
          <div className="stat-sub">child chunk</div>
        </div>
      </div>
      <div className="card stat-card">
        <div className="stat-icon">
          <Clock strokeWidth={2} />
        </div>
        <div className="stat-meta">
          <div className="stat-label">Terakhir Diupdate</div>
          <div className="stat-value" style={{ fontSize: '15px', marginTop: '4px' }}>
            {lastUpdated.date}
          </div>
          <div className="stat-sub">{lastUpdated.sub}</div>
        </div>
      </div>
    </div>
  );
}
