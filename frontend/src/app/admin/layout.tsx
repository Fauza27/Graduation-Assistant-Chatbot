'use client';

import './admin.css';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getAdminToken } from '@/lib/adminAuth';
import { useAdminStore } from '@/lib/adminStore';
import AdminSidebar from '@/components/admin/AdminSidebar';
import MobileKnowledgeShell from '@/components/admin/MobileKnowledgeShell';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { tree, fetchTree } = useAdminStore();
  const [isMobileViewport, setIsMobileViewport] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  useEffect(() => {
    const token = getAdminToken();
    if (!token) {
      router.push('/admin/login');
      return;
    }
    if (!tree) {
      fetchTree();
    }
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

        {isMobileViewport ? (
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
