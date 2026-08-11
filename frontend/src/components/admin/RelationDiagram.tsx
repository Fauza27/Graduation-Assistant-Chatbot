'use client';

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { ParentNode } from '@/lib/adminTypes';

interface RelationDiagramProps {
  parent: ParentNode | null;
}

export default function RelationDiagram({ parent }: RelationDiagramProps) {
  const [isOpen, setIsOpen] = useState(false);

  if (!parent) return null;

  const kids = parent.children || [];
  const width = Math.max(300, 300);
  const rowH = 26;
  const padTop = 10;
  const height = Math.max(90, kids.length * rowH + padTop * 2);
  const px = 10;
  const py = height / 2;
  const cx = width - 118;

  return (
    <>
      <button 
        className={`relation-toggle ${isOpen ? 'open' : ''}`} 
        onClick={() => setIsOpen(!isOpen)}
        type="button"
      >
        <svg className="icon-sm" viewBox="0 0 24 24">
          <polygon points="12 2 2 7 12 12 22 7 12 2" />
          <polyline points="2 17 12 22 22 17" />
          <polyline points="2 12 12 17 22 12" />
        </svg>
        Lihat relasi Parent → Child
        <ChevronDown className="icon-sm chev" />
      </button>
      <div className={`relation-body ${isOpen ? 'open' : ''}`}>
        <div className="relation-svg-wrap">
          <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet" style={{ minWidth: `${width}px`, width: '100%', height: `${height}px` }}>
            {kids.map((c, i) => {
              const cy = padTop + rowH * i + rowH / 2;
              const midX = (px + 62 + cx) / 2;
              return (
                <g key={c.id}>
                  <path d={`M ${px + 62} ${py} C ${midX} ${py} ${midX} ${cy} ${cx - 5} ${cy}`} stroke="var(--gray-200)" strokeWidth="1.4" fill="none" />
                  <circle cx={cx} cy={cy} r="3.5" fill="var(--purple-primary)" />
                  <text x={cx + 9} y={cy + 3.2} fontSize="9.5" fontFamily="Inter,sans-serif">
                    <tspan fill="#374151" fontWeight="600">{c.id}</tspan>
                    <tspan fill="#6B7280" dx="5">{c.title}</tspan>
                  </text>
                </g>
              );
            })}
            <g>
              <rect x={px} y={py - 15} width="66" height="30" rx="8" fill="var(--purple-muda)" stroke="var(--purple-primary)" strokeWidth="1.1" />
              <text x={px + 33} y={py - 2} textAnchor="middle" fontSize="9" fill="#4C1D95" fontFamily="Inter,sans-serif" fontWeight="700">{parent.parent_id}</text>
              <text x={px + 33} y={py + 9.5} textAnchor="middle" fontSize="7.5" fill="#6D28D9" fontFamily="Inter,sans-serif">{kids.length} child</text>
            </g>
          </svg>
        </div>
      </div>
    </>
  );
}
