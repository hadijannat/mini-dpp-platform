// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import DPPEditorPage from '../pages/DPPEditorPage';

const apiFetchMock = vi.fn();
const tenantApiFetchMock = vi.fn();

vi.mock('react-oidc-context', () => ({
  useAuth: () => ({
    user: { access_token: 'fake-token' },
    isAuthenticated: true,
    signinRedirect: vi.fn(),
  }),
}));

vi.mock('@/lib/tenant', () => ({
  useTenantSlug: () => ['default', vi.fn()],
}));

vi.mock('@/features/epcis/lib/epcisApi', () => ({
  fetchEPCISEvents: vi.fn().mockResolvedValue({ eventList: [] }),
}));

vi.mock('@/lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  tenantApiFetch: (...args: unknown[]) => tenantApiFetchMock(...args),
  getApiErrorMessage: vi.fn().mockResolvedValue('Request failed'),
}));

function okJson(data: unknown) {
  return {
    ok: true,
    json: async () => data,
  };
}

function renderEditor() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/console/dpps/019c42a4-128f-7bd9-a95c-a842746f2f9a']}>
        <Routes>
          <Route path="/console/dpps/:dppId" element={<DPPEditorPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

type DppAccess = {
  can_read: boolean;
  can_update: boolean;
  can_publish: boolean;
  can_archive: boolean;
  source: 'owner' | 'share' | 'tenant_admin';
};

function buildDpp(status: string, access: DppAccess) {
  return {
    id: '019c42a4-128f-7bd9-a95c-a842746f2f9a',
    status,
    owner_subject: 'publisher-sub',
    visibility_scope: 'owner_team',
    owner: { subject: 'publisher-sub', display_name: null, email_masked: null },
    access,
    asset_ids: {
      manufacturerPartId: 'publish-2026-04097',
      serialNumber: 'sn-001',
      globalAssetId: 'urn:asset:sn-001',
    },
    qr_payload: null as string | null,
    created_at: '2026-02-10T12:00:00Z',
    updated_at: '2026-02-10T12:00:00Z',
    current_revision_no: 1,
    digest_sha256: 'abc123',
    aas_environment: {
      submodels: [
        {
          id: 'urn:dpp:sm:np',
          idShort: 'Nameplate',
          semanticId: { keys: [{ value: 'urn:semantic:digital-nameplate' }] },
          submodelElements: [],
        },
      ],
    },
    submodel_bindings: [
      {
        submodel_id: 'urn:dpp:sm:np',
        id_short: 'Nameplate',
        semantic_id: 'urn:semantic:digital-nameplate',
        template_key: 'digital-nameplate',
        binding_source: 'semantic_exact',
        support_status: 'supported',
      },
    ],
  };
}

function defaultTenantResponse(path: string) {
  if (path.endsWith('/revisions')) {
    return okJson([]);
  }
  if (path.includes('/diff?')) {
    return okJson({ from_rev: 1, to_rev: 2, added: [], removed: [], changed: [] });
  }
  return okJson({ eventList: [] });
}

describe('DPPEditorPage action gating', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();

    apiFetchMock.mockImplementation((path: string) => {
      if (path === '/api/v1/templates') {
        return Promise.resolve(
          okJson({
            templates: [
              {
                id: '1',
                template_key: 'digital-nameplate',
                semantic_id: 'urn:semantic:digital-nameplate',
                idta_version: '3.0.1',
                support_status: 'supported',
                refresh_enabled: true,
              },
              {
                id: '2',
                template_key: 'battery-passport',
                semantic_id: 'urn:semantic:battery-passport',
                idta_version: '1.0.0',
                support_status: 'unavailable',
                refresh_enabled: false,
              },
            ],
          }),
        );
      }
      return Promise.resolve(okJson({}));
    });
  });

  it('enables draft owner actions and keeps unavailable template add disabled', async () => {
    tenantApiFetchMock.mockImplementation((path: string) => {
      if (path === '/dpps/019c42a4-128f-7bd9-a95c-a842746f2f9a') {
        return Promise.resolve(
          okJson(
            buildDpp('draft', {
              can_read: true,
              can_update: true,
              can_publish: true,
              can_archive: true,
              source: 'owner',
            }),
          ),
        );
      }
      return Promise.resolve(defaultTenantResponse(path));
    });

    renderEditor();

    await waitFor(() => {
      expect(screen.getByTestId('dpp-refresh-rebuild')).toBeTruthy();
    });

    expect((screen.getByRole('button', { name: /publish/i }) as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByTestId('dpp-refresh-rebuild') as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByRole('button', { name: /capture event/i }) as HTMLButtonElement).disabled).toBe(false);

    const addBattery = screen.getByTestId('submodel-add-battery-passport');
    expect((addBattery as HTMLButtonElement).disabled).toBe(true);
  });

  it('disables mutable draft actions for shared read-only access', async () => {
    tenantApiFetchMock.mockImplementation((path: string) => {
      if (path === '/dpps/019c42a4-128f-7bd9-a95c-a842746f2f9a') {
        return Promise.resolve(
          okJson(
            buildDpp('draft', {
              can_read: true,
              can_update: false,
              can_publish: false,
              can_archive: false,
              source: 'share',
            }),
          ),
        );
      }
      return Promise.resolve(defaultTenantResponse(path));
    });

    renderEditor();

    await waitFor(() => {
      expect(screen.getByTestId('dpp-refresh-rebuild')).toBeTruthy();
    });

    expect((screen.getByRole('button', { name: /publish/i }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId('dpp-refresh-rebuild') as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: /capture event/i }) as HTMLButtonElement).disabled).toBe(true);

    expect((screen.getByTestId('submodel-edit-digital-nameplate') as HTMLButtonElement).disabled).toBe(true);
  });

  it('shows QR export only when DPP is published and readable', async () => {
    tenantApiFetchMock.mockImplementation((path: string) => {
      if (path === '/dpps/019c42a4-128f-7bd9-a95c-a842746f2f9a') {
        const published = buildDpp('published', {
          can_read: true,
          can_update: false,
          can_publish: false,
          can_archive: false,
          source: 'share',
        });
        published.qr_payload = JSON.stringify({ dpp_id: published.id });
        return Promise.resolve(
          okJson(published),
        );
      }
      return Promise.resolve(defaultTenantResponse(path));
    });

    renderEditor();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /export/i })).toBeTruthy();
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /export/i }));
    expect(await screen.findByText(/QR Code/i)).toBeTruthy();
  });

  it('blocks refresh/rebuild when archived even if can_update is true', async () => {
    tenantApiFetchMock.mockImplementation((path: string) => {
      if (path === '/dpps/019c42a4-128f-7bd9-a95c-a842746f2f9a') {
        return Promise.resolve(
          okJson(
            buildDpp('archived', {
              can_read: true,
              can_update: true,
              can_publish: true,
              can_archive: true,
              source: 'tenant_admin',
            }),
          ),
        );
      }
      return Promise.resolve(defaultTenantResponse(path));
    });

    renderEditor();

    await waitFor(() => {
      expect(screen.getByTestId('dpp-refresh-rebuild')).toBeTruthy();
    });

    expect((screen.getByTestId('dpp-refresh-rebuild') as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole('button', { name: /publish/i })).toBeNull();
  });

  it('disables read-derived actions when can_read is false', async () => {
    tenantApiFetchMock.mockImplementation((path: string) => {
      if (path === '/dpps/019c42a4-128f-7bd9-a95c-a842746f2f9a') {
        return Promise.resolve(
          okJson(
            buildDpp('published', {
              can_read: false,
              can_update: false,
              can_publish: false,
              can_archive: false,
              source: 'share',
            }),
          ),
        );
      }
      return Promise.resolve(defaultTenantResponse(path));
    });

    renderEditor();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /export/i })).toBeTruthy();
    });

    expect((screen.getByRole('button', { name: /export/i }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/View all events/i)).toBeTruthy();
  });
});
