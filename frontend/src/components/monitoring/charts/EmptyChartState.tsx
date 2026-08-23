'use client';

import { FileSearch } from 'lucide-react';

export default function EmptyChartState({ message }: { message?: string }) {
  return (
    <div className="empty-state" style={{ padding: '30px 14px', minHeight: 150 }}>
      <div className="empty-icon">
        <FileSearch style={{ width: 24, height: 24 }} />
      </div>
      <h3>Belum ada data</h3>
      <p>{message || 'Tidak ada data pada periode ini.'}</p>
    </div>
  );
}
