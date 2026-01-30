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
  if (response.status === 401) {
    return 'Session expired. Please sign in again.';
  }
  if (response.status === 403) {
    return 'You do not have permission to perform this action.';
  }
  const contentType = response.headers.get('content-type') ?? '';
  const rawText = await response.text();
  if (contentType.includes('application/json')) {
    try {
      const body = JSON.parse(rawText) as {
        detail?: string | { errors?: Array<Record<string, unknown>> };
        errors?: Array<Record<string, unknown>>;
      };
      const detail = body?.detail;
      if (typeof detail === 'string') {
        return detail || rawText || fallback;
      }
      const errors = Array.isArray(body?.errors)
        ? body.errors
        : Array.isArray((detail as { errors?: Array<Record<string, unknown>> })?.errors)
          ? (detail as { errors?: Array<Record<string, unknown>> }).errors ?? []
          : [];
      if (errors.length > 0) {
        const messages = errors
          .map((entry) => {
            const name = typeof entry.name === 'string' ? entry.name : '';
            const code = typeof entry.code === 'string' ? entry.code : '';
            const path =
              typeof entry.path === 'string'
                ? entry.path
                : Array.isArray(entry.paths)
                  ? (entry.paths[0] as { jsonPointer?: string })?.jsonPointer ?? ''
                  : '';
            const suffix = [code, name, path].filter(Boolean).join(': ');
            return suffix || JSON.stringify(entry);
          })
          .filter(Boolean)
          .join(' | ');
        return messages || rawText || fallback;
      }
      if (detail && typeof detail === 'object') {
        const message =
          typeof (detail as { message?: string }).message === 'string'
            ? (detail as { message?: string }).message
            : '';
        const id =
          typeof (detail as { dpp_id?: string }).dpp_id === 'string'
            ? (detail as { dpp_id?: string }).dpp_id
            : '';
        if (message && id) {
          return `${message} (DPP: ${id})`;
        }
        if (message) {
          return message;
        }
        return JSON.stringify(detail);
      }
      return rawText || fallback;
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
