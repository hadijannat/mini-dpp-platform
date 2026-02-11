// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
  getApiErrorMessage: vi.fn().mockResolvedValue('Failed to rebuild submodel'),
}));

function okJson(data: unknown) {
  return {
    ok: true,
    json: async () => data,
  };
}

function failedJson() {
  return {
    ok: false,
    json: async () => ({}),
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

describe('DPPEditorPage refresh & rebuild', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    apiFetchMock.mockImplementation((path: string) => {
      if (path === '/api/v1/templates') {
        return Promise.resolve(
          okJson({
            templates: [
              {
                template_key: 'carbon-footprint',
                semantic_id: 'urn:semantic:carbon-footprint',
              },
              {
                template_key: 'digital-nameplate',
                semantic_id: 'urn:semantic:digital-nameplate',
              },
            ],
          }),
        );
      }
      if (path === '/api/v1/templates/refresh') {
        return Promise.resolve(
          okJson({
            templates: [
              {
                template_key: 'carbon-footprint',
                semantic_id: 'urn:semantic:carbon-footprint',
              },
              {
                template_key: 'digital-nameplate',
                semantic_id: 'urn:semantic:digital-nameplate',
              },
            ],
          }),
        );
      }
      return Promise.resolve(failedJson());
    });

    tenantApiFetchMock.mockImplementation((path: string, options?: { body?: string; method?: string }) => {
      if (path === '/dpps/019c42a4-128f-7bd9-a95c-a842746f2f9a') {
        return Promise.resolve(
          okJson({
            id: '019c42a4-128f-7bd9-a95c-a842746f2f9a',
            status: 'draft',
            owner_subject: 'publisher-sub',
            visibility_scope: 'owner_team',
            owner: { subject: 'publisher-sub', display_name: null, email_masked: null },
            access: {
              can_read: true,
              can_update: true,
              can_publish: true,
              can_archive: true,
              source: 'owner',
            },
            asset_ids: {
              manufacturerPartId: 'publish-2026-04097',
              serialNumber: 'sn-001',
              globalAssetId: 'urn:asset:sn-001',
            },
            qr_payload: null,
            created_at: '2026-02-10T12:00:00Z',
            updated_at: '2026-02-10T12:00:00Z',
            current_revision_no: 1,
            digest_sha256: null,
            aas_environment: {
              submodels: [
                {
                  idShort: 'CarbonFootprint',
                  semanticId: { keys: [{ value: 'urn:semantic:carbon-footprint' }] },
                  submodelElements: [],
                },
                {
                  idShort: 'Nameplate',
                  semanticId: { keys: [{ value: 'urn:semantic:digital-nameplate' }] },
                  submodelElements: [],
                },
              ],
            },
          }),
        );
      }

      if (path === '/dpps/019c42a4-128f-7bd9-a95c-a842746f2f9a/submodel' && options?.method === 'PUT') {
        const payload = JSON.parse(options.body ?? '{}') as { template_key?: string };
        if (payload.template_key === 'carbon-footprint') {
          return Promise.resolve(failedJson());
        }
        return Promise.resolve(okJson({ ok: true }));
      }

      return Promise.resolve(failedJson());
    });
  });

  it('shows partial failure summary with failed template keys', async () => {
    renderEditor();

    await waitFor(() => {
      expect(screen.getByTestId('dpp-refresh-rebuild')).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId('dpp-refresh-rebuild'));

    await waitFor(() => {
      expect(
        screen.getByText(/Refresh & Rebuild partially failed for templates: carbon-footprint/i),
      ).toBeTruthy();
    });
  });
});
