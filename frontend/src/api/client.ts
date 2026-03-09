import { useStore } from '../store/useStore';

export async function fetchApi<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = useStore.getState().token;
  const res = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export async function uploadFile(
  path: string,
  file: File,
): Promise<Response> {
  const token = useStore.getState().token;
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(path, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Upload failed: ${res.status}`);
  }
  return res;
}

export async function uploadProductInChat(
  sessionId: string,
  file: File,
): Promise<{ image_path: string; url: string }> {
  const token = useStore.getState().token;
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`/api/v1/sessions/${sessionId}/upload-product`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}

export function fetchChatSSE(
  sessionId: string,
  message: string,
  signal?: AbortSignal,
): Promise<Response> {
  const token = useStore.getState().token;
  return fetch(`/api/v1/sessions/${sessionId}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message }),
    signal,
  });
}
