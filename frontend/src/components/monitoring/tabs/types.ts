import type { QueryLogRow, StageKey } from '@/lib/monitoringTypes';

export interface ListModalState {
  title: string;
  subtitle?: string;
  rows: QueryLogRow[];
  highlightStage?: StageKey;
}

export interface MonTabProps {
  days: number;
  queryLog: QueryLogRow[];
  queryLogLoading: boolean;
  openDetail: (requestId: string) => void;
  openList: (config: ListModalState) => void;
}
