// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
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

function DestinationCapture() {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  return (
    <div>
      <div data-testid="dest-path">{location.pathname}</div>
      <div data-testid="dest-submodel">{params.get('submodel_id') ?? ''}</div>
      <div data-testid="dest-focus-path">{params.get('focus_path') ?? ''}</div>
      <div data-testid="dest-focus-id-short">{params.get('focus_id_short') ?? ''}</div>
    </div>
  );
}

function renderEditor() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/console/dpps/dpp-1']}>
        <Routes>
          <Route path="/console/dpps/:dppId" element={<DPPEditorPage />} />
          <Route
            path="/console/dpps/:dppId/edit/:templateKey"
            element={<DestinationCapture />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('DPPEditorPage outline integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    apiFetchMock.mockImplementation((path: string) => {
      if (path === '/api/v1/templates') {
        return Promise.resolve(
          okJson({
            templates: [
              {
                id: 'template-1',
                template_key: 'digital-nameplate',
                semantic_id: 'urn:semantic:digital-nameplate',
                idta_version: '3.0.1',
                support_status: 'supported',
                refresh_enabled: true,
              },
            ],
          }),
        );
      }
      return Promise.resolve(okJson({}));
    });

    tenantApiFetchMock.mockImplementation((path: string) => {
      if (path === '/dpps/dpp-1') {
        return Promise.resolve(
          okJson({
            id: 'dpp-1',
            status: 'draft',
            access: {
              can_read: true,
              can_update: true,
              can_publish: true,
              can_archive: true,
              source: 'owner',
            },
            asset_ids: {
              manufacturerPartId: 'part-1',
            },
            aas_environment: {
              submodels: [
                {
                  id: 'urn:submodel:nameplate',
                  idShort: 'Nameplate',
                  semanticId: { keys: [{ value: 'urn:semantic:digital-nameplate' }] },
                  submodelElements: [
                    {
                      modelType: 'SubmodelElementCollection',
                      idShort: 'ManufacturerData',
                      value: [
                        {
                          modelType: 'Property',
                          idShort: 'ManufacturerName',
                          value: 'ACME',
                        },
                      ],
                    },
                  ],
                },
              ],
            },
            submodel_bindings: [
              {
                submodel_id: 'urn:submodel:nameplate',
                id_short: 'Nameplate',
                semantic_id: 'urn:semantic:digital-nameplate',
                template_key: 'digital-nameplate',
                binding_source: 'semantic_exact',
                support_status: 'supported',
              },
            ],
          }),
        );
      }
      if (path.endsWith('/revisions')) {
        return Promise.resolve(okJson([]));
      }
      if (path.includes('/diff?')) {
        return Promise.resolve(
          okJson({ from_rev: 1, to_rev: 2, added: [], removed: [], changed: [] }),
        );
      }
      return Promise.resolve(okJson({}));
    });
  });

  it('renders outline pane and compact summary cards instead of inline submodel trees', async () => {
    renderEditor();

    await waitFor(() => {
      expect(screen.getByTestId('dpp-outline-editor-desktop')).toBeTruthy();
    });

    expect(screen.getByText('Sections')).toBeTruthy();
    expect(screen.getByText('Leaf Fields')).toBeTruthy();
    expect(screen.getByText('Validation Signals')).toBeTruthy();
    expect(screen.queryByRole('tree', { name: /Nameplate structure/i })).toBeNull();
  });

  it('navigates to submodel editor with focus query params when a tree node is selected', async () => {
    renderEditor();

    const outlinePane = await waitFor(() =>
      screen.getByTestId('dpp-outline-editor-desktop'),
    );

    fireEvent.click(
      within(outlinePane).getByRole('treeitem', { name: /ManufacturerData/i }),
    );

    await waitFor(() => {
      expect(screen.getByTestId('dest-path').textContent).toBe(
        '/console/dpps/dpp-1/edit/digital-nameplate',
      );
    });

    expect(screen.getByTestId('dest-submodel').textContent).toBe('urn:submodel:nameplate');
    expect(screen.getByTestId('dest-focus-path').textContent).toBe('ManufacturerData');
    expect(screen.getByTestId('dest-focus-id-short').textContent).toBe('ManufacturerData');
  });
});
