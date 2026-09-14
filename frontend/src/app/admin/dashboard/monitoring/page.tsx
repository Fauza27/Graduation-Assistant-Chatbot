'use client';

import { useState } from 'react';
import {
  LayoutDashboard, Gauge, ShieldAlert, Search, Coins, Users, HeartPulse, RefreshCw,
} from 'lucide-react';
import { useMetric } from '@/lib/useMetric';
import { getQueryLog } from '@/lib/monitoringApi';
import type { StageKey } from '@/lib/monitoringTypes';
import type { ListModalState } from '@/components/monitoring/tabs/types';
import ListDrilldownModal from '@/components/monitoring/ListDrilldownModal';
import QueryDetailModal from '@/components/monitoring/QueryDetailModal';
import OverviewTab from '@/components/monitoring/tabs/OverviewTab';
import PerformanceTab from '@/components/monitoring/tabs/PerformanceTab';
import ReliabilityTab from '@/components/monitoring/tabs/ReliabilityTab';
import RetrievalTab from '@/components/monitoring/tabs/RetrievalTab';
import CostTab from '@/components/monitoring/tabs/CostTab';
import UsageTab from '@/components/monitoring/tabs/UsageTab';
import HealthTab from '@/components/monitoring/tabs/HealthTab';
import '../../monitoring.css';

const TABS = [
  { id: 'overview', label: 'Ringkasan', icon: LayoutDashboard, Component: OverviewTab },
  { id: 'performance', label: 'Performa & Latency', icon: Gauge, Component: PerformanceTab },
  { id: 'reliability', label: 'Keandalan & Error', icon: ShieldAlert, Component: ReliabilityTab },
  { id: 'retrieval', label: 'Retrieval & RAG', icon: Search, Component: RetrievalTab },
  { id: 'cost', label: 'Biaya & Token', icon: Coins, Component: CostTab },
  { id: 'usage', label: 'Penggunaan & Bisnis', icon: Users, Component: UsageTab },
  { id: 'health', label: 'Kesehatan Sistem', icon: HeartPulse, Component: HealthTab },
] as const;

export default function MonitoringPage() {
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]['id']>('overview');
  const [days, setDays] = useState(7);
  const [detailRequestId, setDetailRequestId] = useState<string | null>(null);
  const [listModal, setListModal] = useState<ListModalState | null>(null);

  const queryLogQuery = useMetric(() => getQueryLog(days, 500), [days]);
  const queryLog = queryLogQuery.data || [];

  const openDetail = (requestId: string) => setDetailRequestId(requestId);
  const openList = (config: { title: string; subtitle?: string; rows: typeof queryLog; highlightStage?: StageKey }) =>
    setListModal(config);

  const ActiveComponent = TABS.find((t) => t.id === activeTab)?.Component || OverviewTab;

  return (
    <div>
      <div className="mon-page-header">
        <div>
          <h1>Monitoring</h1>
          <p>Performa, keandalan, kualitas retrieval, biaya, penggunaan, dan kesehatan sistem chatbot.</p>
        </div>
        <div className="mon-toolbar">
          <select className="mon-days-select" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={1}>24 jam terakhir</option>
            <option value={7}>7 hari terakhir</option>
            <option value={14}>14 hari terakhir</option>
            <option value={30}>30 hari terakhir</option>
          </select>
          <button
            className={`mon-refresh-btn${queryLogQuery.loading ? ' loading' : ''}`}
            onClick={() => queryLogQuery.reload()}
          >
            <RefreshCw /> Refresh
          </button>
        </div>
      </div>

      <div className="mon-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`mon-tab-btn${activeTab === t.id ? ' active' : ''}`}
            onClick={() => setActiveTab(t.id)}
          >
            <t.icon />
            {t.label}
          </button>
        ))}
      </div>

      <ActiveComponent
        days={days}
        queryLog={queryLog}
        queryLogLoading={queryLogQuery.loading}
        openDetail={openDetail}
        openList={openList}
      />

      <ListDrilldownModal
        open={!!listModal}
        onClose={() => setListModal(null)}
        title={listModal?.title || ''}
        subtitle={listModal?.subtitle}
        rows={listModal?.rows || []}
        highlightStage={listModal?.highlightStage}
        onOpenDetail={(id) => {
          setListModal(null);
          setDetailRequestId(id);
        }}
      />
      <QueryDetailModal key={detailRequestId} requestId={detailRequestId} onClose={() => setDetailRequestId(null)} />
    </div>
  );
}
