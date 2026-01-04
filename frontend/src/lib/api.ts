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
  const headers = withAuthHeaders(token, options.headers ?? {});
  return fetch(url, {
    ...options,
    headers,
  });
}
