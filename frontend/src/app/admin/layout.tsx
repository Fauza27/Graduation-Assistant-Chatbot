'use client';

import './admin.css';
import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { getAdminToken, refreshAdminToken } from '@/lib/adminAuth';
import { useAdminStore } from '@/lib/adminStore';
import AdminSidebar from '@/components/admin/AdminSidebar';
import MobileKnowledgeShell from '@/components/admin/MobileKnowledgeShell';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { tree, fetchTree } = useAdminStore();
  const [isMobileViewport, setIsMobileViewport] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  // Shell drill-down 3-kolom khusus itu didesain untuk Kelola Knowledge Base.
  // Rute lain (mis. Monitoring) sudah responsive sendiri lewat CSS masing-masing,
  // jadi harus tetap render `children` biasa, bukan shell KB.
  const isKnowledgeBaseRoute = !pathname?.includes('/admin/dashboard/monitoring')
    && !pathname?.includes('/admin/dashboard/evaluations');

  useEffect(() => {
    const initialize = async () => {
      const token = getAdminToken() || await refreshAdminToken();
      if (!token) {
        router.push('/admin/login');
        return;
      }
      if (!tree) await fetchTree();
    };
    void initialize();
    const handleResize = () => {
      setIsMobileViewport(window.innerWidth < 768);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [tree, fetchTree, router]);

  return (
    <>
      <div
        className={`sidebar-overlay ${isMobileOpen ? 'show' : ''}`}
        onClick={() => setIsMobileOpen(false)}
      />
      <div className="app show">
        <aside className={`sidebar ${isMobileOpen ? 'show' : ''}`}>
          <AdminSidebar onCloseMobile={() => setIsMobileOpen(false)} />
        </aside>

        {isMobileViewport && isKnowledgeBaseRoute ? (
          <MobileKnowledgeShell />
        ) : (
          <main className="main-panel" id="mainPanel">
            {children}
          </main>
        )}
      </div>
    </>
  );
}
