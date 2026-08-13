'use client';

import { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Database, LogOut, ChevronUp, X } from 'lucide-react';
import { adminLogout, getAdminInfo } from '@/lib/adminAuth';

interface AdminSidebarProps {
  onCloseMobile?: () => void;
}

export default function AdminSidebar({ onCloseMobile }: AdminSidebarProps) {
  const router = useRouter();
  const pathname = usePathname();
  // Get admin info on mount (derived state pattern)
  const adminInfo = getAdminInfo();
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  const handleLogout = () => {
    adminLogout();
    router.push('/admin/login');
  };

  const initial = adminInfo?.full_name ? adminInfo.full_name.substring(0, 2).toUpperCase() : 'AD';
  const name = adminInfo?.full_name || 'Administrator';
  const role = 'Administrator';

  return (
    <>
      <div className="sidebar-header">
        <svg className="brand-mark" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
          <circle cx="20" cy="20" r="19" fill="#F5F1FC" />
          <circle cx="20" cy="20" r="13" fill="none" stroke="#6D28D9" strokeWidth="2" />
          <circle cx="20" cy="20" r="4" fill="#6D28D9" />
        </svg>
        <div className="brand-text">
          <div className="b1">STMIK</div>
          <div className="b2">WIDYA CIPTA DHARMA</div>
        </div>
        {onCloseMobile && (
          <button className="icon-btn sidebar-close" onClick={onCloseMobile} aria-label="Tutup menu">
            <X className="icon-sm" />
          </button>
        )}
      </div>

      <nav className="sidebar-nav">
        <button
          className={`nav-item ${pathname?.includes('/admin/dashboard') ? 'active' : ''}`}
          type="button"
          onClick={() => {
            router.push('/admin/dashboard');
            if (onCloseMobile) onCloseMobile();
          }}
        >
          <Database className="icon" />
          <span>Kelola Knowledge Base</span>
        </button>
      </nav>

      <div className="sidebar-footer">
        <button className="nav-item nav-item-danger" onClick={handleLogout} type="button">
          <LogOut className="icon" />
          <span>Logout</span>
        </button>
        <div style={{ position: 'relative' }}>
          <button
            className="profile-card"
            type="button"
            aria-haspopup="true"
            aria-expanded={isProfileOpen}
            onClick={() => setIsProfileOpen(!isProfileOpen)}
          >
            <div className="profile-avatar">{initial}</div>
            <div className="profile-meta">
              <div className="name">{name}</div>
              <div className="role">{role}</div>
            </div>
            <ChevronUp className="icon-sm" />
          </button>
          <div className={`profile-dropdown ${isProfileOpen ? 'show' : ''}`}>
            <button type="button" onClick={handleLogout}>
              <LogOut className="icon-sm" />
              <span>Keluar</span>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
