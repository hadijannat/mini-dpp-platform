import { describe, expect, it, vi, afterEach } from 'vitest';

import { apiFetch, getApiErrorMessage, withAuthHeaders } from './api';

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

// ---------------------------------------------------------------------------
// getApiErrorMessage
// ---------------------------------------------------------------------------

/**
 * Build a minimal Response-like object that satisfies getApiErrorMessage.
 */
function mockResponse(
  status: number,
  body: string,
  contentType: string = 'application/json',
): Response {
  return {
    status,
    headers: {
      get(name: string) {
        if (name.toLowerCase() === 'content-type') return contentType;
        return null;
      },
    },
    text: () => Promise.resolve(body),
  } as unknown as Response;
}

describe('getApiErrorMessage', () => {
  it('returns session-expired message for 401', async () => {
    const res = mockResponse(401, '');
    expect(await getApiErrorMessage(res, 'fallback')).toBe(
      'Session expired. Please sign in again.',
    );
  });

  it('returns permission-denied message for 403', async () => {
    const res = mockResponse(403, '');
    expect(await getApiErrorMessage(res, 'fallback')).toBe(
      'You do not have permission to perform this action.',
    );
  });

  it('extracts a string detail from JSON body', async () => {
    const res = mockResponse(422, JSON.stringify({ detail: 'some error' }));
    expect(await getApiErrorMessage(res, 'fallback')).toBe('some error');
  });

  it('formats an error array from detail.errors', async () => {
    const body = {
      detail: {
        errors: [{ code: 'INVALID', name: 'field' }],
      },
    };
    const res = mockResponse(422, JSON.stringify(body));
    const msg = await getApiErrorMessage(res, 'fallback');
    expect(msg).toContain('INVALID');
    expect(msg).toContain('field');
  });

  it('formats detail object with message and dpp_id', async () => {
    const body = {
      detail: { message: 'Already exists', dpp_id: 'abc-123' },
    };
    const res = mockResponse(409, JSON.stringify(body));
    expect(await getApiErrorMessage(res, 'fallback')).toBe(
      'Already exists (DPP: abc-123)',
    );
  });

  it('formats detail object with only message', async () => {
    const body = { detail: { message: 'Something went wrong' } };
    const res = mockResponse(500, JSON.stringify(body));
    expect(await getApiErrorMessage(res, 'fallback')).toBe('Something went wrong');
  });

  it('falls back to raw text for non-JSON content type', async () => {
    const res = mockResponse(500, 'Server Error', 'text/plain');
    expect(await getApiErrorMessage(res, 'fallback')).toBe('Server Error');
  });

  it('uses fallback when body is empty', async () => {
    const res = mockResponse(500, '', 'text/plain');
    expect(await getApiErrorMessage(res, 'default error')).toBe('default error');
  });

  it('handles malformed JSON gracefully', async () => {
    const res = mockResponse(500, '{not-valid-json', 'application/json');
    // Should not throw; falls back to raw text
    expect(await getApiErrorMessage(res, 'fallback')).toBe('{not-valid-json');
  });

  it('falls back when detail is an empty string', async () => {
    const body = JSON.stringify({ detail: '' });
    const res = mockResponse(422, body);
    const msg = await getApiErrorMessage(res, 'fallback');
    // empty string detail -> `detail || rawText || fallback`
    expect(msg).toBe(body);
  });
});
