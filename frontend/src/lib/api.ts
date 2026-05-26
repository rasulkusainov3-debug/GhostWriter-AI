const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export type ApiErrorPayload = {
  code: string;
  message: string;
  field?: string;
  fields?: Record<string, string>;
};

export class ApiError extends Error {
  status: number;
  code?: string;
  field?: string;
  fields?: Record<string, string>;

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = payload.code;
    this.field = payload.field;
    this.fields = payload.fields;
  }
}

export function errorMessage(error: unknown, fallback = 'Request failed') {
  return error instanceof ApiError || error instanceof Error ? error.message : fallback;
}

function pickApiError(body: unknown, fallback: string): ApiErrorPayload {
  if (!body || typeof body !== 'object') return { code: 'REQUEST_FAILED', message: fallback };
  const record = body as { error?: unknown; detail?: unknown };
  const direct = record.error;
  if (direct && typeof direct === 'object') {
    const error = direct as Partial<ApiErrorPayload>;
    return {
      code: error.code || 'REQUEST_FAILED',
      message: error.message || fallback,
      field: error.field,
      fields: error.fields,
    };
  }
  const detail = record.detail;
  if (detail && typeof detail === 'object' && 'error' in detail) {
    return pickApiError(detail, fallback);
  }
  if (typeof detail === 'string') return { code: 'REQUEST_FAILED', message: detail };
  return { code: 'REQUEST_FAILED', message: fallback };
}

export function getToken() {
  return localStorage.getItem('ghostwriter_token');
}

export function setToken(token: string) {
  localStorage.setItem('ghostwriter_token', token);
}

export function clearToken() {
  localStorage.removeItem('ghostwriter_token');
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = pickApiError(body, response.statusText || 'Request failed');
    if (response.status === 401 && ['TOKEN_EXPIRED', 'INVALID_TOKEN', 'UNAUTHORIZED'].includes(error.code)) {
      clearToken();
      localStorage.setItem('ghostwriter_auth_notice', error.code);
    }
    throw new ApiError(response.status, error);
  }
  return response.json();
}
