const DEFAULT_API_BASE = import.meta.env.PROD ? '/api' : 'http://127.0.0.1:5000/api';
const API_BASE = (import.meta.env.VITE_API_URL || DEFAULT_API_BASE).replace(/\/$/, '');
const CSRF_STORAGE_KEY = 'folioport_admin_csrf';
const MUTATION_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export function getCsrfToken() {
  return typeof window === 'undefined' ? null : window.sessionStorage.getItem(CSRF_STORAGE_KEY);
}

export function setCsrfToken(token) {
  if (typeof window === 'undefined') return;
  if (token) window.sessionStorage.setItem(CSRF_STORAGE_KEY, token);
  else window.sessionStorage.removeItem(CSRF_STORAGE_KEY);
}

export function clearAuth() {
  setCsrfToken(null);
}

export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const method = (options.method || 'GET').toUpperCase();
  const csrfToken = getCsrfToken();
  if (MUTATION_METHODS.has(method) && csrfToken) headers.set('X-CSRF-TOKEN', csrfToken);
  let body = options.body;
  if (body !== undefined && !(body instanceof FormData) && typeof body !== 'string') {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(body);
  }
  const response = await fetch(`${API_BASE}${path.startsWith('/') ? path : `/${path}`}`, {
    ...options, method, headers, body, credentials: 'include',
  });
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof payload === 'object' && payload?.error ? payload.error : `Request failed (${response.status}).`;
    if (response.status === 401 && !path.startsWith('/auth/login')) {
      clearAuth();
      if (typeof window !== 'undefined') window.dispatchEvent(new Event('folioport:auth-expired'));
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return payload;
}

export async function apiStream(path, body, onToken, onStatus = () => {}) {
  const headers = new Headers({ 'Content-Type': 'application/json' });
  const csrfToken = getCsrfToken();
  if (csrfToken) headers.set('X-CSRF-TOKEN', csrfToken);
  const response = await fetch(`${API_BASE}${path.startsWith('/') ? path : `/${path}`}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    credentials: 'include',
  });
  if (!response.ok) {
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : null;
    if (response.status === 401 && !path.startsWith('/auth/login')) {
      clearAuth();
      if (typeof window !== 'undefined') window.dispatchEvent(new Event('folioport:auth-expired'));
    }
    const error = new Error(payload?.error || `Request failed (${response.status}).`);
    error.status = response.status;
    throw error;
  }
  if (!response.body) throw new Error('The AI stream is unavailable in this browser.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finished = false;
  const consumeEvent = (block) => {
    let eventName = 'message';
    const data = [];
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) eventName = line.slice(6).trim();
      else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
    }
    if (!data.length) return;
    let payload;
    try {
      payload = JSON.parse(data.join('\n'));
    } catch {
      throw new Error('The AI stream returned invalid data.');
    }
    if (eventName === 'error') throw new Error(payload.error || 'The AI stream failed.');
    if (eventName === 'done') {
      finished = true;
      return;
    }
    if (eventName === 'status' && typeof payload.status === 'string') {
      onStatus(payload.status);
      return;
    }
    if (typeof payload.token === 'string') onToken(payload.token);
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        buffer += decoder.decode();
        break;
      }
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        consumeEvent(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf('\n\n');
      }
    }
    if (buffer.trim()) consumeEvent(buffer);
  } finally {
    reader.releaseLock();
  }
  if (!finished) throw new Error('The AI stream ended before the response was complete.');
}
