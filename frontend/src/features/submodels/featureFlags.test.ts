// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { resolveSubmodelUxRollout } from './featureFlags';

afterEach(() => {
  vi.unstubAllEnvs();
  window.localStorage.clear();
});

describe('resolveSubmodelUxRollout', () => {
  it('enables all surfaces when globally enabled with no canary restriction', () => {
    vi.stubEnv('VITE_SUBMODEL_UX_ENABLED', 'true');
    vi.stubEnv('VITE_SUBMODEL_UX_CANARY_TENANTS', '');

    const rollout = resolveSubmodelUxRollout('default');

    expect(rollout.enabled).toBe(true);
    expect(rollout.surfaces).toEqual({
      publisher: true,
      editor: true,
      viewer: true,
    });
  });

  it('enables only canary tenant when canary list is configured', () => {
    vi.stubEnv('VITE_SUBMODEL_UX_ENABLED', 'true');
    vi.stubEnv('VITE_SUBMODEL_UX_CANARY_TENANTS', 'canary-a,canary-b');

    const allowed = resolveSubmodelUxRollout('canary-a');
    const blocked = resolveSubmodelUxRollout('default');

    expect(allowed.enabled).toBe(true);
    expect(allowed.isCanaryTenant).toBe(true);
    expect(blocked.enabled).toBe(false);
    expect(blocked.surfaces).toEqual({
      publisher: false,
      editor: false,
      viewer: false,
    });
  });

  it('supports tenant-specific surface overrides', () => {
    vi.stubEnv('VITE_SUBMODEL_UX_ENABLED', 'true');
    vi.stubEnv('VITE_SUBMODEL_UX_CANARY_TENANTS', 'alpha');
    vi.stubEnv('VITE_SUBMODEL_UX_TENANT_SURFACES', '{"alpha":["publisher","viewer"]}');

    const rollout = resolveSubmodelUxRollout('alpha');
    expect(rollout.surfaces).toEqual({
      publisher: true,
      editor: false,
      viewer: true,
    });
  });

  it('prioritizes local storage override for test/canary control', () => {
    vi.stubEnv('VITE_SUBMODEL_UX_ENABLED', 'false');
    window.localStorage.setItem(
      'dpp.submodelUxRollout.override',
      JSON.stringify({
        default: {
          publisher: true,
          editor: false,
          viewer: true,
        },
      }),
    );

    const rollout = resolveSubmodelUxRollout('default');

    expect(rollout.source).toBe('override');
    expect(rollout.enabled).toBe(true);
    expect(rollout.surfaces).toEqual({
      publisher: true,
      editor: false,
      viewer: true,
    });
  });
});
