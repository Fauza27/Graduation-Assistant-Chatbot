'use client';

import './admin.css';
import { useEffect, useRef, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Menu } from 'lucide-react';
import { getAdminToken, refreshAdminToken } from '@/lib/adminAuth';
import { useAdminStore } from '@/lib/adminStore';
import AdminSidebar from '@/components/admin/AdminSidebar';
import MobileKnowledgeShell from '@/components/admin/MobileKnowledgeShell';
import styles from './adminShell.module.css';

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const tree = useAdminStore((state) => state.tree);
  const fetchTree = useAdminStore((state) => state.fetchTree);
  const [authenticated, setAuthenticated] = useState(false);
  const [isMobileViewport, setIsMobileViewport] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const sidebarRef = useRef<HTMLElement>(null);
  const menuRef = useRef<HTMLButtonElement>(null);
  const isLoginPage = pathname === '/admin/login';
  const isKnowledgeBaseRoute = pathname === '/admin/dashboard';
  const drawerOpen = isMobileViewport && isMobileOpen;
  const pageTitle = pathname?.includes('/evaluations')
    ? 'Evaluasi RAG'
    : pathname?.includes('/monitoring')
      ? 'Monitoring'
      : 'Kelola Knowledge Base';

  useEffect(() => {
    if (isLoginPage) return;
    let cancelled = false;
    const initialize = async () => {
      try {
        const token = getAdminToken() || (await refreshAdminToken());
        if (cancelled) return;
        if (!token) {
          router.replace('/admin/login');
          return;
        }
        setAuthenticated(true);
      } catch {
        if (!cancelled) router.replace('/admin/login');
      }
    };
    void initialize();
    return () => {
      cancelled = true;
    };
  }, [isLoginPage, router]);

  useEffect(() => {
    if (!isLoginPage && authenticated && isKnowledgeBaseRoute && !tree)
      void fetchTree();
  }, [isLoginPage, authenticated, isKnowledgeBaseRoute, tree, fetchTree]);

  useEffect(() => {
    const media = window.matchMedia('(max-width: 767px)');
    const update = () => setIsMobileViewport(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    if (!drawerOpen) return;
    const menuButton = menuRef.current;
    sidebarRef.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsMobileOpen(false);
        return;
      }
      if (event.key !== 'Tab') return;
      const buttons = Array.from(
        sidebarRef.current?.querySelectorAll<HTMLButtonElement>(
          'button:not(:disabled)',
        ) || [],
      ).filter(
        (button) =>
          button.getClientRects().length > 0 &&
          getComputedStyle(button).visibility === 'visible',
      );
      const first = buttons[0];
      const last = buttons[buttons.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('keydown', handleKey);
      if (menuButton?.isConnected) menuButton.focus();
    };
  }, [drawerOpen]);

  if (isLoginPage) return <>{children}</>;
  if (!authenticated)
    return (
      <div className={styles.loading} role="status">
        Memeriksa sesi admin…
      </div>
    );

  return (
    <>
      <button
        type="button"
        tabIndex={-1}
        aria-label="Tutup navigasi admin"
        className={`sidebar-overlay ${drawerOpen ? 'show' : ''}`}
        style={{ border: 0, padding: 0 }}
        onClick={() => setIsMobileOpen(false)}
      />
      <div className="app show">
        <aside
          ref={sidebarRef}
          className={`sidebar ${isMobileViewport ? (drawerOpen ? 'open' : 'collapsed') : ''}`}
          inert={isMobileViewport && !drawerOpen}
          aria-label="Navigasi admin"
          role={isMobileViewport ? 'dialog' : undefined}
          aria-modal={drawerOpen || undefined}
        >
          <AdminSidebar
            onCloseMobile={
              isMobileViewport ? () => setIsMobileOpen(false) : undefined
            }
          />
        </aside>
        <main className="main-panel" id="mainPanel" inert={drawerOpen}>
          {isMobileViewport && (
            <header className={styles.mobileHeader}>
              <button
                ref={menuRef}
                type="button"
                className="icon-btn"
                aria-label="Buka navigasi admin"
                aria-expanded={drawerOpen}
                onClick={() => setIsMobileOpen(true)}
              >
                <Menu size={20} />
              </button>
              <h2>{pageTitle}</h2>
            </header>
          )}
          <div
            className={`${styles.content} ${pathname?.includes('/monitoring') ? styles.monitoringContent : ''}`}
          >
            {isMobileViewport && isKnowledgeBaseRoute ? (
              <MobileKnowledgeShell />
            ) : (
              children
            )}
          </div>
        </main>
      </div>
    </>
  );
}
