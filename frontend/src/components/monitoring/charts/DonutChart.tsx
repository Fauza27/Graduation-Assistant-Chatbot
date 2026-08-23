'use client';

import { useState } from 'react';
import { fmtThousand } from '@/lib/monitoringUtils';

export interface DonutSlice {
  label: string;
  value: number;
  pct: number;
  color: string;
}

interface DonutChartProps {
  data: DonutSlice[];
  size?: number;
  stroke?: number;
  unitLabel?: string;
  totalLabel?: string;
}

export default function DonutChart({ data, size = 150, stroke = 20, unitLabel = 'pertanyaan', totalLabel }: DonutChartProps) {
  const [hover, setHover] = useState<DonutSlice | null>(null);
  const total = data.reduce((a, d) => a + d.value, 0) || 1;
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * r;

  const segLens = data.map((d) => (d.value / total) * circ);
  const arcs = data.map((d, i) => ({
    ...d,
    len: Math.max(segLens[i] - 3, 0),
    offset: segLens.slice(0, i).reduce((a, b) => a + b, 0),
  }));

  const center = hover
    ? { pct: hover.pct, label: hover.label, value: `${fmtThousand(hover.value)} ${unitLabel}` }
    : totalLabel
      ? { pct: null, label: totalLabel, value: `${fmtThousand(total)} ${unitLabel}` }
      : null;

  return (
    <div className="donut-wrap">
      <div className="donut-svg-box" style={{ width: size, height: size }}>
        <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
          {arcs.map((d) => (
            <circle
              key={d.label}
              className="donut-hit"
              cx={cx}
              cy={cy}
              r={r}
              fill="none"
              stroke={d.color}
              strokeWidth={stroke}
              strokeDasharray={`${d.len} ${circ - d.len}`}
              strokeDashoffset={-d.offset}
              transform={`rotate(-90 ${cx} ${cy})`}
              strokeLinecap="round"
              style={{ cursor: 'default' }}
              onMouseEnter={() => setHover(d)}
              onMouseLeave={() => setHover(null)}
            />
          ))}
        </svg>
        {center && (
          <div className="donut-center">
            {center.pct != null && <b>{center.pct}%</b>}
            <span>{center.label}</span>
            <span>{center.value}</span>
          </div>
        )}
      </div>
      <div className="donut-legend">
        {data.map((d) => (
          <div className="donut-legend-item" key={d.label}>
            <span className="donut-legend-dot" style={{ background: d.color }} />
            <span className="dl-label">{d.label}</span>
            <span className="dl-pct">{d.pct}%</span>
            <span className="dl-val">({fmtThousand(d.value)})</span>
          </div>
        ))}
      </div>
    </div>
  );
}
