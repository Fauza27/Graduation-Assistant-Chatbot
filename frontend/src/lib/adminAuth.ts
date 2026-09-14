import { API_BASE_URL } from './apiConfig';

export async function adminLogin(username: string, password: string, rememberMe: boolean) {
  const url = `${API_BASE_URL}/api/admin/login`;
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password, remember_me: rememberMe }),
    });

    if (response.status === 401) {
      return { success: false, message: 'Username atau password salah.' };
    }

    if (!response.ok) {
      return { success: false, message: 'Gagal melakukan login. Silakan coba lagi.' };
    }

    const data = await response.json();
    const storage = rememberMe ? localStorage : sessionStorage;

    localStorage.removeItem('admin_access_token');
    localStorage.removeItem('admin_info');
    sessionStorage.removeItem('admin_access_token');
    sessionStorage.removeItem('admin_info');
    storage.setItem('admin_access_token', data.access_token);
    storage.setItem('admin_info', JSON.stringify(data.admin));

    return { success: true };
  } catch (error) {
    console.error('Admin login error:', error);
    return { success: false, message: 'Tidak bisa terhubung ke server.' };
  }
}

export function getAdminToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('admin_access_token') || sessionStorage.getItem('admin_access_token') || null;
}

export async function refreshAdminToken(): Promise<string | null> {
  const url = `${API_BASE_URL}/api/admin/refresh`;
  const response = await fetch(url, { method: 'POST', credentials: 'include' });
  if (!response.ok) return null;
  const data = await response.json();
  if (typeof data.access_token !== 'string') return null;

  const storage = localStorage.getItem('admin_access_token') ? localStorage : sessionStorage;
  storage.setItem('admin_access_token', data.access_token);
  return data.access_token;
}

interface AdminInfo {
  full_name: string;
  username: string;
}

export function getAdminInfo(): AdminInfo | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem('admin_info') || sessionStorage.getItem('admin_info');
  if (raw) {
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }
  return null;
}

export function adminLogout() {
  if (typeof window === 'undefined') return;
  
  const token = getAdminToken();
  const url = `${API_BASE_URL}/api/admin/logout`;
  const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
  void fetch(url, {
    method: 'POST',
    credentials: 'include',
    keepalive: true,
    headers,
  }).catch(() => undefined);

  // Remove from both to be safe
  localStorage.removeItem('admin_access_token');
  localStorage.removeItem('admin_info');
  sessionStorage.removeItem('admin_access_token');
  sessionStorage.removeItem('admin_info');

}
