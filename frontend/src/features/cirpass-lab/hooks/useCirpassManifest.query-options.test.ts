import { beforeEach, describe, expect, it, vi } from 'vitest';

const useQueryMock = vi.fn();
const apiFetchMock = vi.fn();
const getApiErrorMessageMock = vi.fn();
const parseManifestMock = vi.fn();
const loadGeneratedManifestMock = vi.fn();

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: unknown) => useQueryMock(options),
}));

vi.mock('@/lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  getApiErrorMessage: (...args: unknown[]) => getApiErrorMessageMock(...args),
}));

vi.mock('../schema/manifestLoader', () => ({
  parseCirpassLabManifest: (...args: unknown[]) => parseManifestMock(...args),
  loadGeneratedCirpassManifest: (...args: unknown[]) => loadGeneratedManifestMock(...args),
}));

import { useCirpassManifest } from './useCirpassManifest';

function makeOkResponse(payload: Record<string, unknown>) {
  return {
    ok: true,
    json: async () => payload,
  };
}

describe('useCirpassManifest query options', () => {
  beforeEach(() => {
    useQueryMock.mockReset();
    apiFetchMock.mockReset();
    getApiErrorMessageMock.mockReset();
    parseManifestMock.mockReset();
    loadGeneratedManifestMock.mockReset();

    useQueryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
  });

  it('resolves from API payload when endpoint succeeds', async () => {
    const parsedManifest = {
      manifest_version: 'v1.0.0',
      story_version: 'V3.1',
      generated_at: '2026-02-14T00:00:00Z',
      source_status: 'fresh',
      stories: [],
      feature_flags: {
        scenario_engine_enabled: true,
        live_mode_enabled: false,
        inspector_enabled: true,
      },
    };

    apiFetchMock.mockResolvedValue(makeOkResponse({ manifest_version: 'v1.0.0' }));
    parseManifestMock.mockReturnValue(parsedManifest);

    useCirpassManifest();
    const queryConfig = useQueryMock.mock.calls[0]?.[0] as {
      queryFn: () => Promise<Record<string, unknown>>;
    };

    const payload = await queryConfig.queryFn();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/public/cirpass/lab/manifest/latest');
    expect(payload).toEqual({
      manifest: parsedManifest,
      resolved_from: 'api',
    });
  });

  it('falls back to generated manifest when API request fails', async () => {
    const generatedManifest = {
      manifest_version: 'v1.0.0',
      story_version: 'V3.1',
      generated_at: '2026-02-14T00:00:00Z',
      source_status: 'fresh',
      stories: [],
      feature_flags: {
        scenario_engine_enabled: true,
        live_mode_enabled: false,
        inspector_enabled: true,
      },
    };

    apiFetchMock.mockRejectedValue(new Error('network error'));
    loadGeneratedManifestMock.mockReturnValue(generatedManifest);

    useCirpassManifest();
    const queryConfig = useQueryMock.mock.calls[0]?.[0] as {
      queryFn: () => Promise<Record<string, unknown>>;
    };

    const payload = await queryConfig.queryFn();
    expect(payload).toEqual({
      manifest: generatedManifest,
      resolved_from: 'generated',
      warning: 'Scenario manifest service unavailable. Running bundled manifest.',
    });
  });

  it('falls back to generated manifest when API responds with non-ok status', async () => {
    const generatedManifest = {
      manifest_version: 'v1.0.0',
      story_version: 'V3.1',
      generated_at: '2026-02-14T00:00:00Z',
      source_status: 'fresh',
      stories: [],
      feature_flags: {
        scenario_engine_enabled: true,
        live_mode_enabled: false,
        inspector_enabled: true,
      },
    };

    apiFetchMock.mockResolvedValue({
      ok: false,
      status: 503,
    });
    getApiErrorMessageMock.mockResolvedValue('manifest unavailable');
    loadGeneratedManifestMock.mockReturnValue(generatedManifest);

    useCirpassManifest();
    const queryConfig = useQueryMock.mock.calls[0]?.[0] as {
      queryFn: () => Promise<Record<string, unknown>>;
    };

    const payload = await queryConfig.queryFn();
    expect(getApiErrorMessageMock).toHaveBeenCalledTimes(1);
    expect(payload).toEqual({
      manifest: generatedManifest,
      resolved_from: 'generated',
      warning: 'Scenario manifest service unavailable. Running bundled manifest.',
    });
  });
});
