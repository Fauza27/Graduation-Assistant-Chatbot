import { getAuthToken, logout, refreshAuthToken } from './auth';
import { CitationSource, ChatMessage } from './store';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

export interface ChatResponse {
  answer: string;
  num_docs: number;
  session_id: string;
  sources: (CitationSource | string)[];
  intent?: string | null;
  confidence?: number | null;
  reasoning?: string | null;
  error?: string | null;
}

export interface SessionItem {
  session_id: string;
  title: string;
  last_access: string;
  [key: string]: unknown;
}

export interface SessionsResponse {
  ok?: boolean;
  sessions: SessionItem[];
}

export interface SessionDetailResponse {
  ok?: boolean;
  messages: ChatMessage[];
}

export interface DeleteSessionResponse {
  ok?: boolean;
  message?: string;
}

export interface UserProfileResponse {
  mahasiswa_id?: string;
  nama: string;
  email: string;
  avatar_url: string | null;
}

let refreshPromise: Promise<string | null> | null = null;

async function getOrRefreshToken(): Promise<string | null> {
  const currentToken = getAuthToken();
  if (currentToken) return currentToken;
  refreshPromise ||= refreshAuthToken().finally(() => { refreshPromise = null; });
  return refreshPromise;
}

async function fetchWithAuth<T = unknown>(endpoint: string, options: RequestInit = {}, retry = true): Promise<T> {
  const token = await getOrRefreshToken();
  if (!token) {
    logout();
    throw new Error('Not authenticated');
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
    ...(options.headers as Record<string, string>),
  };

  if (options.body instanceof FormData) {
    delete headers['Content-Type'];
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (response.status === 401 && retry) {
    refreshPromise ||= refreshAuthToken().finally(() => { refreshPromise = null; });
    const refreshedToken = await refreshPromise;
    if (refreshedToken) {
      return fetchWithAuth<T>(endpoint, options, false);
    }
  }

  if (response.status === 401) {
    logout();
    throw new Error('Session expired');
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    let errorMessage = `HTTP error ${response.status}`;

    if (typeof errorData.detail === 'string') {
      errorMessage = errorData.detail;
    } else if (Array.isArray(errorData.detail)) {
      errorMessage = errorData.detail
        .map((err: { msg?: string }) => (err.msg ? err.msg.replace(/^Value error,\s*/i, '') : JSON.stringify(err)))
        .join(', ');
    } else if (errorData.message) {
      errorMessage = errorData.message;
    }

    throw new Error(errorMessage);
  }

  if (response.status === 204) {
    return {} as T;
  }

  const data = await response.json().catch(() => ({}));
  return data as T;
}

export async function sendChatMessage(query: string, session_id: string): Promise<ChatResponse> {
  return fetchWithAuth<ChatResponse>('/api/ai/chat', {
    method: 'POST',
    body: JSON.stringify({
      query,
      session_id,
      channel: 'website',
    }),
  });
}

export async function fetchSessions(): Promise<SessionsResponse> {
  return fetchWithAuth<SessionsResponse>('/api/sessions/');
}

export async function fetchSessionDetails(id: string): Promise<SessionDetailResponse> {
  return fetchWithAuth<SessionDetailResponse>(`/api/sessions/${id}`);
}

export async function deleteSession(id: string): Promise<DeleteSessionResponse> {
  return fetchWithAuth<DeleteSessionResponse>(`/api/sessions/${id}`, {
    method: 'DELETE',
  });
}

export async function fetchProfile(): Promise<UserProfileResponse> {
  return fetchWithAuth<UserProfileResponse>('/api/auth/me');
}
