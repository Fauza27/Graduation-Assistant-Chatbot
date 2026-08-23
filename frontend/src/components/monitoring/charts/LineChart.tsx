'use client';

import { useState } from 'react';
import EmptyChartState from './EmptyChartState';

export interface LineSeries {
  name: string;
  values: number[];
  color: string;
  dashed?: boolean;
}

interface LineChartProps {
  labels: string[];
  series: LineSeries[];
  height?: number;
  area?: boolean;
  valueFormatter?: (v: number) => string;
}

function niceStep(max: number): number {
  if (max <= 10) return 2;
  if (max <= 50) return 10;
  if (max <= 200) return 40;
  if (max <= 1000) return 200;
  if (max <= 3000) return 500;
  const mag = Math.pow(10, Math.floor(Math.log10(max)) - 1);
  return mag * 2;
}

export default function LineChart({ labels, series, height = 190, area, valueFormatter }: LineChartProps) {
  const [activeIdx, setActiveIdx] = useState<number | null>(null);
  const fmt = valueFormatter || ((v: number) => String(Math.round(v)));

  if (!labels.length || !series.length) return <EmptyChartState />;

  const w = 640;
  const h = height;
  const padL = 44;
  const padR = 12;
  const padT = 16;
  const padB = 28;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;

  const allVals = series.flatMap((s) => s.values);
  const maxRaw = Math.max(...allVals, 0);
  const step = niceStep(maxRaw * 1.15);
  const niceMax = Math.ceil((maxRaw * 1.15) / step) * step || step;
  const n = labels.length;
  const stepX = n > 1 ? plotW / (n - 1) : 0;

  const X = (i: number) => padL + i * stepX;
  const Y = (v: number) => padT + plotH - (v / niceMax) * plotH;

  const gridCount = 4;
  const gridLines = Array.from({ length: gridCount + 1 }, (_, g) => {
    const gv = (niceMax * g) / gridCount;
    return { y: Y(gv), label: fmt(gv) };
  });

  return (
    <div className="linechart-wrap">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} style={{ display: 'block', overflow: 'visible' }}>
        {gridLines.map((g, i) => (
          <g key={i}>
            <line x1={padL} y1={g.y} x2={w - padR} y2={g.y} stroke="var(--gray-100)" strokeWidth={1} />
            <text x={padL - 9} y={g.y + 4} textAnchor="end" fontSize={11.5} fill="var(--gray-500)">
              {g.label}
            </text>
          </g>
        ))}
        {labels.map((lb, i) => (
          <text key={i} x={X(i)} y={h - 6} textAnchor="middle" fontSize={11.5} fill="var(--gray-500)">
            {lb}
          </text>
        ))}

        {series.map((s, si) => {
          const pts = s.values.map((v, i) => `${X(i)},${Y(v)}`);
          const lineD = `M ${pts.join(' L ')}`;
          const gid = `lg-${si}`;
          return (
            <g key={s.name}>
              {area && si === 0 && (
                <>
                  <defs>
                    <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={s.color} stopOpacity={0.25} />
                      <stop offset="100%" stopColor={s.color} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <path
                    d={`${lineD} L ${X(n - 1)},${padT + plotH} L ${X(0)},${padT + plotH} Z`}
                    fill={`url(#${gid})`}
                    stroke="none"
                  />
                </>
              )}
              <path
                d={lineD}
                fill="none"
                stroke={s.color}
                strokeWidth={2.5}
                strokeLinejoin="round"
                strokeLinecap="round"
                strokeDasharray={s.dashed ? '5 4' : undefined}
              />
              {s.values.map((v, i) => (
                <circle key={i} cx={X(i)} cy={Y(v)} r={3.25} fill="var(--white)" stroke={s.color} strokeWidth={2.25} />
              ))}
            </g>
          );
        })}

        {labels.map((_, i) => (
          <circle
            key={i}
            className="chart-hit"
            cx={X(i)}
            cy={Y(series[0]?.values[i] ?? 0)}
            r={13}
            fill="transparent"
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => setActiveIdx(i)}
            onMouseLeave={() => setActiveIdx(null)}
            onClick={() => setActiveIdx((cur) => (cur === i ? null : i))}
          />
        ))}
      </svg>

      {activeIdx != null && (
        <div
          className="chart-tooltip show"
          style={{ left: `${(X(activeIdx) / w) * 100}%`, top: `${(Y(series[0]?.values[activeIdx] ?? 0) / h) * 100}%` }}
        >
          <div className="tt-date">{labels[activeIdx]}</div>
          {series.map((s) => (
            <div className="tt-val" key={s.name}>
              {s.name}: <strong>{fmt(s.values[activeIdx])}</strong>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
