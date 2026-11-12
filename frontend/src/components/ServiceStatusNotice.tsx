'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { CircleAlert, LoaderCircle } from 'lucide-react';

type ServiceStatus = 'checking' | 'ready' | 'unavailable';

export function useServiceStatus() {
  const [status, setStatus] = useState<ServiceStatus>('checking');
  const pending = useRef<AbortController | null>(null);

  const probe = useCallback(async () => {
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;

    const timeout = setTimeout(() => controller.abort(), 25_000);
    let available = false;
    try {
      const response = await fetch('/api/service-status', {
        cache: 'no-store',
        signal: controller.signal,
      });
      available = response.ok && (await response.json()).available === true;
    } catch {
      // Treat a failed connection as unavailable and let the user check again.
    } finally {
      clearTimeout(timeout);
    }
    if (pending.current === controller) {
      pending.current = null;
      setStatus(available ? 'ready' : 'unavailable');
    }
  }, []);

  const check = useCallback(() => {
    setStatus('checking');
    void probe();
  }, [probe]);

  const markUnavailable = useCallback(() => {
    pending.current?.abort();
    pending.current = null;
    setStatus('unavailable');
  }, []);

  useEffect(() => {
    void probe();
    return () => {
      pending.current?.abort();
      pending.current = null;
    };
  }, [probe]);

  return { status, check, markUnavailable };
}

export default function ServiceStatusNotice({ status, onRetry }: {
  status: ServiceStatus;
  onRetry: () => void;
}) {
  if (status === 'ready') return null;

  const checking = status === 'checking';
  const Icon = checking ? LoaderCircle : CircleAlert;

  return (
    <div className={`service-notice${checking ? '' : ' service-notice-unavailable'}`}>
      <Icon aria-hidden="true" size={19} className={checking ? 'service-notice-spin' : undefined} />
      <div>
        <div role="status">
          <strong>{checking ? 'Menyiapkan layanan chatbot' : 'Server belum bisa dihubungi'}</strong>
          <p>{checking
            ? 'Halaman akan siap setelah server merespons.'
            : 'Tunggu sebentar, lalu periksa kembali status server.'}</p>
        </div>
        {!checking && <button type="button" onClick={onRetry}>Periksa lagi</button>}
      </div>
    </div>
  );
}
