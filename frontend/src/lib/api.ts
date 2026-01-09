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

export async function apiFetch(
  url: string,
  options: RequestInit = {},
  token?: string
): Promise<Response> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, '') ?? '';
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
