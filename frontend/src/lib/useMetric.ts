'use client';

import { useCallback, useEffect, useState } from 'react';

interface MetricResult<T> {
  key: string;
  data: T | null;
  error: string | null;
}

export function useMetric<T>(fetcher: () => Promise<{ data: T }>, deps: unknown[]) {
  const [reloadTick, setReloadTick] = useState(0);
  const [result, setResult] = useState<MetricResult<T> | null>(null);
  const key = JSON.stringify([...deps, reloadTick]);

  useEffect(() => {
    let cancelled = false;
    fetcher()
      .then((res) => {
        if (!cancelled) setResult({ key, data: res.data, error: null });
      })
      .catch((err) => {
        if (!cancelled) {
          setResult({ key, data: null, error: err instanceof Error ? err.message : 'Gagal memuat data.' });
        }
      });
    return () => {
      cancelled = true;
    };
    // `fetcher` sengaja tidak dimasukkan ke deps: closure-nya sudah selalu
    // dibuat ulang mengikuti `deps` (mis. `days`) oleh komponen pemanggil,
    // dan `key` di bawah sudah mencerminkan seluruh `deps` + reloadTick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const loading = result?.key !== key;
  const data = result?.key === key ? result.data : null;
  const error = result?.key === key ? result.error : null;
  const reload = useCallback(() => setReloadTick((t) => t + 1), []);

  return { data, loading, error, reload };
}
