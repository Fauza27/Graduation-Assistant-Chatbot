'use client';

import { useState } from 'react';
import EmptyChartState from './EmptyChartState';
import { fmtCompact } from '@/lib/monitoringUtils';

export interface VBarItem {
  label: string;
  value: number;
  color?: string;
  unit?: string;
  /** Kalau diisi, bar ini bisa diklik untuk drill-down (mis. skor cross-encoder). */
  onClick?: () => void;
}

export default function VBarChart({ items, height = 220 }: { items: VBarItem[]; height?: number }) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  if (!items.length) return <EmptyChartState />;

  const w = 480;
  const h = height;
  const padL = 40;
  const padR = 14;
  const padT = 16;
  const padB = 32;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;
  const n = items.length;
  const maxV = Math.max(...items.map((i) => i.value), 0) || 1;
  const niceMax = Math.ceil((maxV * 1.15) / 50) * 50 || maxV * 1.15;
  const gap = 10;
  const barW = (plotW - gap * (n - 1)) / n;
  const Y = (v: number) => padT + plotH - (v / niceMax) * plotH;

  const gridCount = 4;

  return (
    <div className="linechart-wrap">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} style={{ display: 'block', overflow: 'visible' }}>
        {Array.from({ length: gridCount + 1 }, (_, g) => {
          const gv = (niceMax * g) / gridCount;
          const gy = Y(gv);
          return (
            <g key={g}>
              <line x1={padL} y1={gy} x2={w - padR} y2={gy} stroke="var(--gray-100)" strokeWidth={1} />
              <text x={padL - 9} y={gy + 4} textAnchor="end" fontSize={11} fill="var(--gray-500)">
                {fmtCompact(gv)}
              </text>
            </g>
          );
        })}
        {items.map((it, i) => {
          const x = padL + i * (barW + gap);
          const y = Y(it.value);
          const barH = padT + plotH - y;
          return (
            <g key={i}>
              <rect
                className="chart-hit"
                x={x}
                y={y}
                width={barW}
                height={Math.max(barH, 1)}
                rx={4}
                fill={it.color || 'var(--purple-primary)'}
                style={{ cursor: it.onClick ? 'pointer' : 'default' }}
                onMouseEnter={() => setHoverIdx(i)}
                onMouseLeave={() => setHoverIdx(null)}
                onClick={it.onClick}
              />
              <text x={x + barW / 2} y={h - 8} textAnchor="middle" fontSize={10.5} fill="var(--gray-500)">
                {it.label}
              </text>
            </g>
          );
        })}
      </svg>
      {hoverIdx != null && (
        <div
          className="chart-tooltip show"
          style={{
            left: `${((padL + hoverIdx * (barW + gap) + barW / 2) / w) * 100}%`,
            top: `${(Y(items[hoverIdx].value) / h) * 100}%`,
          }}
        >
          <div className="tt-date">{items[hoverIdx].label}</div>
          <div className="tt-val">
            {items[hoverIdx].unit || 'jumlah'}: <strong>{fmtCompact(items[hoverIdx].value)}</strong>
          </div>
        </div>
      )}
    </div>
  );
}
