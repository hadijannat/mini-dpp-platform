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

import {
  LANDING_SUMMARY_REFRESH_SLA_MS,
  useLandingSummary,
} from '../useLandingSummary';

function makeOkResponse(payload: Record<string, unknown>) {
  return {
    ok: true,
    json: async () => payload,
  };
}

describe('useLandingSummary query options', () => {
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

  it('uses live polling defaults with global all scope', async () => {
    apiFetchMock.mockResolvedValue(
      makeOkResponse({
        tenant_slug: 'all',
        published_dpps: 1,
        active_product_families: 1,
        dpps_with_traceability: 1,
        latest_publish_at: '2026-02-10T10:00:00Z',
        generated_at: '2026-02-10T10:00:00Z',
        scope: 'all',
        refresh_sla_seconds: 30,
      }),
    );

    useLandingSummary(undefined, 'all');
    const queryConfig = useQueryMock.mock.calls[0]?.[0] as {
      queryKey: unknown[];
      staleTime: number;
      refetchInterval: number;
      refetchIntervalInBackground: boolean;
      queryFn: () => Promise<Record<string, unknown>>;
    };

    expect(queryConfig.queryKey).toEqual(['landing-summary', 'all']);
    expect(queryConfig.staleTime).toBe(0);
    expect(queryConfig.refetchInterval).toBe(LANDING_SUMMARY_REFRESH_SLA_MS);
    expect(queryConfig.refetchIntervalInBackground).toBe(true);

    const data = await queryConfig.queryFn();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/public/landing/summary?scope=all');
    expect(data.tenant_slug).toBe('all');
  });

  it('uses tenant-scoped endpoint when tenant slug is provided', async () => {
    apiFetchMock.mockResolvedValue(
      makeOkResponse({
        tenant_slug: 'default',
        published_dpps: 3,
        active_product_families: 2,
        dpps_with_traceability: 2,
        latest_publish_at: null,
        generated_at: '2026-02-10T10:00:00Z',
        scope: 'default',
        refresh_sla_seconds: 30,
      }),
    );

    useLandingSummary('Default');
    const queryConfig = useQueryMock.mock.calls[0]?.[0] as {
      queryKey: unknown[];
      queryFn: () => Promise<Record<string, unknown>>;
    };

    expect(queryConfig.queryKey).toEqual(['landing-summary', 'default']);
    await queryConfig.queryFn();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/public/default/landing/summary');
  });
});
