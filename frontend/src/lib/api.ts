import { getTenantSlug } from './tenant';

export function withAuthHeaders(
  token?: string,
  headers: HeadersInit = {}
): HeadersInit {
  if (!token) {
    return headers;
  }
  return {
    ...headers,
    Authorization: `Bearer ${token}`,
  };
}

export async function getApiErrorMessage(
  response: Response,
  fallback: string
): Promise<string> {
  if (response.status === 401 || response.status === 403) {
    return 'Session expired. Please sign in again.';
  }
  const contentType = response.headers.get('content-type') ?? '';
  const rawText = await response.text();
  if (contentType.includes('application/json')) {
    try {
      const body = JSON.parse(rawText) as { detail?: string };
      const detail = typeof body?.detail === 'string' ? body.detail : '';
      return detail || rawText || fallback;
    } catch {
      return rawText || fallback;
    }
  }
  return rawText || fallback;
}

export async function apiFetch(
  url: string,
  options: RequestInit = {},
  token?: string
): Promise<Response> {
  const internalApiBaseUrl = import.meta.env.VITE_API_BASE_URL_INTERNAL;
  const internalHostnames = new Set(['dpp-frontend', 'frontend']);
  const hostname = typeof window === 'undefined' ? '' : window.location.hostname;
  const resolvedBaseUrl =
    internalApiBaseUrl && internalHostnames.has(hostname)
      ? internalApiBaseUrl
      : import.meta.env.VITE_API_BASE_URL;
  const baseUrl = resolvedBaseUrl?.replace(/\/+$/, '') ?? '';
  const resolvedUrl =
    baseUrl && !url.startsWith('http')
      ? `${baseUrl}${url.startsWith('/') ? '' : '/'}${url}`
      : url;
  const headers = withAuthHeaders(token, options.headers ?? {});
  return fetch(resolvedUrl, {
    ...options,
    headers,
  });
}

export async function tenantApiFetch(
  path: string,
  options: RequestInit = {},
  token?: string,
  tenantSlug?: string
): Promise<Response> {
  const slug = tenantSlug || getTenantSlug();
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return apiFetch(`/api/v1/tenants/${slug}${normalizedPath}`, options, token);
}
