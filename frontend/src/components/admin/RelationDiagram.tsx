'use client';

import { useState, useMemo } from 'react';
import { ChevronDown } from 'lucide-react';
import { ParentNode } from '@/lib/adminTypes';

interface RelationDiagramProps {
  parent: ParentNode | null;
}

interface DiagramConfig {
  width: number;
  height: number;
  rowHeight: number;
  padding: number;
  parentBox: { width: number; height: number };
}

interface DiagramLayout {
  config: DiagramConfig;
  parentPos: { x: number; y: number };
  childrenPos: Array<{ x: number; y: number; child: any }>;
}

function calculateDiagramLayout(childCount: number): DiagramLayout {
  const config: DiagramConfig = {
    width: Math.max(400, childCount * 20 + 300),
    height: Math.max(120, childCount * 28 + 40),
    rowHeight: 28,
    padding: 20,
    parentBox: { width: 80, height: 32 }
  };

  const parentPos = {
    x: config.padding,
    y: config.height / 2 - config.parentBox.height / 2
  };

  const childrenStartY = config.padding;
  const childrenX = config.width - 140;

  return {
    config,
    parentPos,
    childrenPos: Array.from({ length: childCount }, (_, i) => ({
      x: childrenX,
      y: childrenStartY + i * config.rowHeight + config.rowHeight / 2,
      child: null
    }))
  };
}

function ConnectionPath({ from, to }: { from: { x: number; y: number }; to: { x: number; y: number } }) {
  const midX = (from.x + to.x) / 2;
  const pathData = `M ${from.x} ${from.y} C ${midX} ${from.y} ${midX} ${to.y} ${to.x - 5} ${to.y}`;
  
  return (
    <path 
      d={pathData}
      stroke="var(--gray-200)" 
      strokeWidth="1.5" 
      fill="none" 
    />
  );
}

function ParentBox({ parent, position, config }: { 
  parent: ParentNode; 
  position: { x: number; y: number }; 
  config: DiagramConfig;
}) {
  const { x, y } = position;
  const { width, height } = config.parentBox;
  
  return (
    <g>
      <rect 
        x={x} y={y} 
        width={width} height={height}
        rx="8" 
        fill="var(--purple-muda)" 
        stroke="var(--purple-primary)" 
        strokeWidth="1.2"
      />
      <text 
        x={x + width/2} y={y + 12} 
        textAnchor="middle" 
        fontSize="10" 
        fill="#4C1D95" 
        fontFamily="Inter, sans-serif" 
        fontWeight="600"
      >
        {parent.parent_id}
      </text>
      <text 
        x={x + width/2} y={y + 25} 
        textAnchor="middle" 
        fontSize="8" 
        fill="#6D28D9" 
        fontFamily="Inter, sans-serif"
      >
        {parent.children.length} children
      </text>
    </g>
  );
}

function ChildNode({ child, position, index }: { 
  child: any; 
  position: { x: number; y: number }; 
  index: number;
}) {
  const { x, y } = position;
  
  return (
    <g>
      <circle 
        cx={x} cy={y} 
        r="4" 
        fill="var(--purple-primary)" 
      />
      <text 
        x={x + 12} y={y + 1} 
        fontSize="10" 
        fontFamily="Inter, sans-serif"
      >
        <tspan fill="#374151" fontWeight="600">{child.id}</tspan>
        <tspan fill="#6B7280" dx="6">{child.title}</tspan>
      </text>
    </g>
  );
}

function DiagramContent({ parent }: { parent: ParentNode }) {
  const layout = useMemo(() => calculateDiagramLayout(parent.children.length), [parent.children.length]);
  
  const parentCenter = {
    x: layout.parentPos.x + layout.config.parentBox.width,
    y: layout.parentPos.y + layout.config.parentBox.height / 2
  };

  return (
    <div className="relation-svg-wrap">
      <svg 
        viewBox={`0 0 ${layout.config.width} ${layout.config.height}`}
        preserveAspectRatio="xMidYMid meet"
        style={{ 
          minWidth: `${layout.config.width}px`, 
          width: '100%', 
          height: `${layout.config.height}px` 
        }}
      >
        {parent.children.map((child, index) => (
          <ConnectionPath
            key={child.id}
            from={parentCenter}
            to={{ x: layout.childrenPos[index].x, y: layout.childrenPos[index].y }}
          />
        ))}
        
        <ParentBox 
          parent={parent} 
          position={layout.parentPos} 
          config={layout.config} 
        />
        
        {parent.children.map((child, index) => (
          <ChildNode
            key={child.id}
            child={child}
            position={layout.childrenPos[index]}
            index={index}
          />
        ))}
      </svg>
    </div>
  );
}

export default function RelationDiagram({ parent }: RelationDiagramProps) {
  const [isOpen, setIsOpen] = useState(false);

  if (!parent) return null;

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
        <DiagramContent parent={parent} />
      </div>
    </>
  );
}
