
const BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('auth_token');
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
}

function authHeadersFormData(): HeadersInit {
  const token = localStorage.getItem('auth_token');
  // No Content-Type — let the browser set multipart boundary
  return { 'Authorization': `Bearer ${token}` };
}

// ── Stats (user-scoped) ──────────────────────────────────────
export async function fetchStats() {
  const res = await fetch(`${BASE}/stats`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to fetch stats');
  return res.json();
}

// ── Resume upload ────────────────────────────────────────────
export async function uploadResume(formData: FormData) {
  const res = await fetch(`${BASE}/resume/upload`, {
    method: 'POST',
    headers: authHeadersFormData(),
    body: formData,
  });
  if (!res.ok) throw new Error('Upload failed');
  return res.json();
}

// ── Email verification ───────────────────────────────────────
export async function verifyEmail(taskId: string, code: string) {
  const res = await fetch(`${BASE}/resume/verify-email`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ task_id: taskId, code }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || 'Verification failed');
  }
  return res.json();
}

// ── Generic authenticated GET ────────────────────────────────
export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  if (res.status === 401) {
    // Token expired — redirect to login
    localStorage.removeItem('auth_token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) throw new Error(`Request failed: ${path}`);
  return res.json();
}

// ── Generic authenticated POST ───────────────────────────────
export async function apiPost<T>(path: string, body: object): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (res.status === 401) {
    localStorage.removeItem('auth_token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed: ${path}`);
  }
  return res.json();
}