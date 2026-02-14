import { beforeEach, describe, expect, it, vi } from 'vitest';

const useQueryMock = vi.fn();
const apiFetchMock = vi.fn();
const getApiErrorMessageMock = vi.fn();

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: unknown) => useQueryMock(options),
}));

vi.mock('@/lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  getApiErrorMessage: (...args: unknown[]) => getApiErrorMessageMock(...args),
}));

import { useRegulatoryTimeline } from '../useRegulatoryTimeline';

function makeOkResponse(payload: Record<string, unknown>) {
  return {
    ok: true,
    json: async () => payload,
  };
}

describe('useRegulatoryTimeline query options', () => {
  beforeEach(() => {
    useQueryMock.mockReset();
    apiFetchMock.mockReset();
    getApiErrorMessageMock.mockReset();
    useQueryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
  });

  it('uses expected defaults for all-track query', async () => {
    apiFetchMock.mockResolvedValue(
      makeOkResponse({
        generated_at: '2026-02-10T10:00:00Z',
        fetched_at: '2026-02-10T10:00:00Z',
        source_status: 'fresh',
        refresh_sla_seconds: 82800,
        digest_sha256: 'a'.repeat(64),
        events: [],
      }),
    );

    useRegulatoryTimeline('all');

    const queryConfig = useQueryMock.mock.calls[0]?.[0] as {
      queryKey: unknown[];
      staleTime: number;
      gcTime: number;
      retry: number;
      enabled: boolean;
      queryFn: () => Promise<Record<string, unknown>>;
    };

    expect(queryConfig.queryKey).toEqual(['regulatory-timeline', 'all']);
    expect(queryConfig.staleTime).toBe(5 * 60 * 1000);
    expect(queryConfig.gcTime).toBe(60 * 60 * 1000);
    expect(queryConfig.retry).toBe(1);
    expect(queryConfig.enabled).toBe(true);

    await queryConfig.queryFn();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/public/landing/regulatory-timeline');
  });

  it('uses filtered track endpoint for standards', async () => {
    apiFetchMock.mockResolvedValue(
      makeOkResponse({
        generated_at: '2026-02-10T10:00:00Z',
        fetched_at: '2026-02-10T10:00:00Z',
        source_status: 'fresh',
        refresh_sla_seconds: 82800,
        digest_sha256: 'b'.repeat(64),
        events: [],
      }),
    );

    useRegulatoryTimeline('standards');

    const queryConfig = useQueryMock.mock.calls[0]?.[0] as {
      queryKey: unknown[];
      queryFn: () => Promise<Record<string, unknown>>;
    };

    expect(queryConfig.queryKey).toEqual(['regulatory-timeline', 'standards']);

    await queryConfig.queryFn();
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/api/v1/public/landing/regulatory-timeline?track=standards',
    );
  });

  it('can disable fetch in deferred contexts', () => {
    useRegulatoryTimeline('regulation', false);

    const queryConfig = useQueryMock.mock.calls[0]?.[0] as {
      enabled: boolean;
    };

    expect(queryConfig.enabled).toBe(false);
  });
});
