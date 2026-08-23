'use client';

import { CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';

export type SystemStatus = 'healthy' | 'degraded' | 'down';

export default function StatusBanner({ status, note }: { status: SystemStatus; note: string }) {
  const cfg = {
    healthy: { icon: CheckCircle2, cls: 'status-banner-ok', title: 'Semua Sistem Normal' },
    degraded: { icon: AlertTriangle, cls: 'status-banner-warn', title: 'Ada Gangguan Ringan Terdeteksi' },
    down: { icon: XCircle, cls: 'status-banner-crit', title: 'Gangguan Signifikan Terdeteksi' },
  }[status];
  const Icon = cfg.icon;

  return (
    <div className={`status-banner ${cfg.cls}`}>
      <Icon style={{ width: 20, height: 20, flexShrink: 0 }} />
      <div>
        <div className="sb-title">{cfg.title}</div>
        <div className="sb-note">{note}</div>
      </div>
    </div>
  );
}
