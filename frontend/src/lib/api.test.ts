import { describe, expect, it, vi, afterEach } from 'vitest';

import { apiFetch, withAuthHeaders } from './api';

describe('withAuthHeaders', () => {
  it('returns original headers when token is missing', () => {
    const headers = { 'Content-Type': 'application/json' };
    expect(withAuthHeaders(undefined, headers)).toEqual(headers);
  });

  it('adds Authorization header when token is provided', () => {
    const headers = { 'X-Test': '1' };
    expect(withAuthHeaders('token-123', headers)).toEqual({
      ...headers,
      Authorization: 'Bearer token-123',
    });
  });
});

describe('apiFetch', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('calls fetch with merged auth headers', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true } as Response);
    vi.stubGlobal('fetch', fetchMock);

    await apiFetch('/api/test', { headers: { 'X-Test': '1' } }, 'token-abc');

    const baseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, '') ?? '';
    const expectedUrl = baseUrl ? `${baseUrl}/api/test` : '/api/test';

    expect(fetchMock).toHaveBeenCalledWith(expectedUrl, {
      headers: {
        'X-Test': '1',
        Authorization: 'Bearer token-abc',
      },
    });
  });
});
