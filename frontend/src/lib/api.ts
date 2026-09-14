import { getAuthToken, logout, refreshAuthToken } from './auth';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

let refreshPromise: Promise<string | null> | null = null;

async function getOrRefreshToken(): Promise<string | null> {
  const currentToken = getAuthToken();
  if (currentToken) return currentToken;
  refreshPromise ||= refreshAuthToken().finally(() => { refreshPromise = null; });
  return refreshPromise;
}

async function fetchWithAuth(endpoint: string, options: RequestInit = {}, retry = true) {
  const token = await getOrRefreshToken();
  if (!token) {
    logout();
    throw new Error('Not authenticated');
  }

  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
    ...options.headers,
  };

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (response.status === 401 && retry) {
    refreshPromise ||= refreshAuthToken().finally(() => { refreshPromise = null; });
    const refreshedToken = await refreshPromise;
    if (refreshedToken) {
      return fetchWithAuth(endpoint, options, false);
    }
  }

  if (response.status === 401) {
    logout();
    throw new Error('Session expired');
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error ${response.status}`);
  }

  return response.json();
}

export async function sendChatMessage(query: string, session_id: string) {
  return fetchWithAuth('/api/ai/chat', {
    method: 'POST',
    body: JSON.stringify({
      query,
      session_id,
      channel: 'website'
    }),
  });
}

export async function fetchSessions() {
  return fetchWithAuth('/api/sessions/');
}

export async function fetchSessionDetails(id: string) {
  return fetchWithAuth(`/api/sessions/${id}`);
}

export async function deleteSession(id: string) {
  return fetchWithAuth(`/api/sessions/${id}`, {
    method: 'DELETE',
  });
}

export async function fetchProfile() {
  return fetchWithAuth('/api/auth/me');
}
