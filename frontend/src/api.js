const API_BASE = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000/api').replace(/\/$/, '');

export function getToken() {
  return localStorage.getItem('folioport_admin_token');
}

export function setToken(token) {
  if (token) localStorage.setItem('folioport_admin_token', token);
  else localStorage.removeItem('folioport_admin_token');
}

export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  let body = options.body;
  if (body !== undefined && !(body instanceof FormData) && typeof body !== 'string') {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(body);
  }
  const response = await fetch(`${API_BASE}${path.startsWith('/') ? path : `/${path}`}`, {
    ...options, headers, body,
  });
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof payload === 'object' && payload?.error ? payload.error : `Request failed (${response.status}).`;
    if (response.status === 401 && !path.startsWith('/auth/login')) {
      setToken(null);
      if (typeof window !== 'undefined') window.dispatchEvent(new Event('folioport:auth-expired'));
    }
    throw new Error(message);
  }
  return payload;
}

export async function apiStream(path, body, onToken, onStatus = () => {}) {
  const headers = new Headers({ 'Content-Type': 'application/json' });
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path.startsWith('/') ? path : `/${path}`}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : null;
    if (response.status === 401 && !path.startsWith('/auth/login')) {
      setToken(null);
      if (typeof window !== 'undefined') window.dispatchEvent(new Event('folioport:auth-expired'));
    }
    throw new Error(payload?.error || `Request failed (${response.status}).`);
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
