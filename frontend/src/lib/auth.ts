import { jwtDecode } from 'jwt-decode';
import { API_BASE_URL } from './apiConfig';
import { useAppStore } from './store';
import { fetchBackend } from './backendAvailability';

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
}

export function setAuthToken(token: string): void {
  if (typeof window === 'undefined') return;
  const previousOwner = tokenOwner(getAuthToken());
  const nextOwner = tokenOwner(token);
  if (!previousOwner || previousOwner !== nextOwner) clearConversation();
  localStorage.setItem('access_token', token);
}

export async function refreshAuthToken(): Promise<string | null> {
  const response = await fetchBackend(`${API_BASE_URL}/api/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
    signal: AbortSignal.timeout(25_000),
  });
  if (!response.ok) return null;
  const data = await response.json();
  if (typeof data.access_token !== 'string') return null;
  setAuthToken(data.access_token);
  return data.access_token;
}

export function logout(): void {
  if (typeof window === 'undefined') return;
  void fetch(`${API_BASE_URL}/api/auth/logout`, {
    method: 'POST',
    credentials: 'include',
    keepalive: true,
  }).catch(() => undefined);
  localStorage.removeItem('access_token');
  clearConversation();
  window.location.href = '/login';
}
function tokenOwner(token: string | null): string | null {
  if (!token) return null;
  try {
    return jwtDecode<{ sub?: string }>(token).sub || null;
  } catch {
    return null;
  }
}

function clearConversation(): void {
  useAppStore.getState().clearConversation();
  useAppStore.persist.clearStorage();
}
