'use client';

export interface HBarItem {
  label: string;
  value: number;
  valueLabel?: string;
  color?: string;
  /** Kalau diisi, baris ini bisa diklik (mis. untuk drill-down per tahap pipeline). */
  onClick?: () => void;
}

export default function HBarList({ items, numbered, max }: { items: HBarItem[]; numbered?: boolean; max?: number }) {
  const maxVal = max || Math.max(...items.map((i) => i.value), 0) || 1;

  return (
    <div className="hbar-list">
      {items.map((it, idx) => {
        const pct = Math.max(2, (it.value / maxVal) * 100);
        const clickable = !!it.onClick;
        return (
          <div
            key={it.label}
            className={`hbar-row${clickable ? ' clickable' : ''}`}
            onClick={it.onClick}
            role={clickable ? 'button' : undefined}
            tabIndex={clickable ? 0 : undefined}
          >
            <div className="hbar-row-top">
              <span className="hb-label">
                {numbered && <span className="hb-step-num">{idx + 1}</span>}
                {it.label}
              </span>
              <span className="hb-value">{it.valueLabel ?? it.value}</span>
            </div>
            <div className="hbar-track">
              <div className="hbar-fill" style={{ width: `${pct}%`, background: it.color }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
