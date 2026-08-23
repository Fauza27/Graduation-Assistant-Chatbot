'use client';

import type { LucideIcon } from 'lucide-react';
import { AlertTriangle } from 'lucide-react';

export type StatColor = 'purple' | 'blue' | 'amber' | 'coral' | 'teal' | 'indigo' | 'emerald' | 'gray';
export type Severity = 'ok' | 'warn' | 'crit';

interface StatCardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  color?: StatColor;
  note?: string;
  /** Kalau diisi, kartu dapat border+ikon warning/danger di ATAS warna dekoratif biasa —
   * ini yang menjawab catatan review desain sebelumnya (kartu sebelumnya statis). */
  severity?: Severity;
  onClick?: () => void;
}

export default function StatCard({ label, value, icon: Icon, color = 'purple', note, severity = 'ok', onClick }: StatCardProps) {
  const clickable = !!onClick;
  return (
    <div
      className={`astat-card astat-${color}${severity !== 'ok' ? ` astat-sev-${severity}` : ''}${clickable ? ' clickable' : ''}`}
      onClick={onClick}
      role={clickable ? 'button' : undefined}
      tabIndex={clickable ? 0 : undefined}
    >
      <div className="astat-icon">
        {severity === 'crit' ? <AlertTriangle style={{ width: 18, height: 18 }} /> : <Icon style={{ width: 18, height: 18 }} />}
      </div>
      <div className="astat-body">
        <span className="astat-label">{label}</span>
        <span className="astat-value">{value}</span>
        {note && <span className="astat-note">{note}</span>}
      </div>
    </div>
  );
}
