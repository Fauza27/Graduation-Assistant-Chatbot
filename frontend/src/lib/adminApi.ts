import { getAdminToken, adminLogout } from './adminAuth';
import { KnowledgeTreeResponse, ChunkDetail, ChunkEditStatus } from './adminTypes';

async function adminFetch(path: string, options: RequestInit = {}) {
  const token = getAdminToken();
  
  if (!token) {
    adminLogout();
    throw new Error('Unauthorized');
  }

  const headers = new Headers(options.headers || {});
  headers.set('Authorization', `Bearer ${token}`);
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const url = `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/admin${path}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    adminLogout();
    throw new Error('Sesi kedaluwarsa. Silakan login kembali.');
  }

  if (response.status === 403) {
    throw new Error('Akun ini bukan admin.');
  }

  if (!response.ok) {
    let errorMessage = `Terjadi kesalahan (Status: ${response.status})`;
    try {
      const data = await response.json();
      if (data.detail) {
        errorMessage = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch (e) {
      // Ignored
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

export async function getKnowledgeTree(): Promise<KnowledgeTreeResponse> {
  return adminFetch('/documents', { method: 'GET' });
}

export async function getChunkDetail(childId: string): Promise<ChunkDetail> {
  return adminFetch(`/chunks/${childId}`, { method: 'GET' });
}

export interface ChunkSaveResponse {
  message: string;
  embedding_status: 'pending' | 'stale' | 'success' | 'failed';
  content_changed: boolean;
}

export async function saveChunk(
  childId: string, 
  updates: { title?: string; pages?: string; content?: string }
): Promise<ChunkSaveResponse> {
  return adminFetch(`/chunks/${childId}`, { 
    method: 'PUT', 
    body: JSON.stringify(updates)
  });
}

export interface ReembedTriggerResponse {
  message: string;
  log_id: string;
  status: 'pending' | 'processing' | 'success' | 'failed';
}

export async function triggerReembed(childId: string): Promise<ReembedTriggerResponse> {
  return adminFetch(`/chunks/${childId}/reembed`, { method: 'POST' });
}

export async function getEditStatus(childId: string): Promise<ChunkEditStatus> {
  return adminFetch(`/chunks/${childId}/edit-status`, { method: 'GET' });
}

export interface DeleteResponse {
  message: string;
  parent_deleted: boolean;
}

export async function deleteChunk(childId: string): Promise<DeleteResponse> {
  return adminFetch(`/chunks/${childId}`, { method: 'DELETE' });
}
