export async function adminLogin(username: string, password: string, rememberMe: boolean) {
  const url = `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/admin/login`;
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password }),
    });

    if (response.status === 401) {
      return { success: false, message: 'Username atau password salah.' };
    }

    if (!response.ok) {
      return { success: false, message: 'Gagal melakukan login. Silakan coba lagi.' };
    }

    const data = await response.json();
    const storage = rememberMe ? localStorage : sessionStorage;
    
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

export function getAdminInfo(): any | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem('admin_info') || sessionStorage.getItem('admin_info');
  if (raw) {
    try {
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }
  return null;
}

export function adminLogout() {
  if (typeof window === 'undefined') return;
  
  // Remove from both to be safe
  localStorage.removeItem('admin_access_token');
  localStorage.removeItem('admin_info');
  sessionStorage.removeItem('admin_access_token');
  sessionStorage.removeItem('admin_info');

  // Optional: ping logout endpoint best-effort
  const url = `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/admin/logout`;
  fetch(url, { method: 'POST' }).catch(() => {});
}
