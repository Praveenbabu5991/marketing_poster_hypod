import { fetchApi } from './client';
import type { ChatMessage, Session, SessionCreate } from '../types';

export function listSessions(brandId?: string): Promise<Session[]> {
  const params = brandId ? `?brand_id=${brandId}` : '';
  return fetchApi<Session[]>(`/api/v1/sessions${params}`);
}

export function getSession(id: string): Promise<Session> {
  return fetchApi<Session>(`/api/v1/sessions/${id}`);
}

export function createSession(data: SessionCreate): Promise<Session> {
  return fetchApi<Session>('/api/v1/sessions', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateSession(id: string, data: { title: string }): Promise<Session> {
  return fetchApi<Session>(`/api/v1/sessions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteSession(id: string): Promise<void> {
  return fetchApi<void>(`/api/v1/sessions/${id}`, { method: 'DELETE' });
}

export function getSessionMessages(id: string): Promise<ChatMessage[]> {
  return fetchApi<ChatMessage[]>(`/api/v1/sessions/${id}/messages`);
}
