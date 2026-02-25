// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import SubmodelEditorPage from '@/features/editor/pages/SubmodelEditorPage';

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

describe('SubmodelEditorPage regression', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    apiFetchMock.mockImplementation((path: string) => {
      if (path === '/api/v1/templates/digital-nameplate') {
        return Promise.resolve(okJson({ template_key: 'digital-nameplate', semantic_id: 'urn:sm' }));
      }
      if (path === '/api/v1/templates/digital-nameplate/contract') {
        return Promise.resolve(
          okJson({
            template_key: 'digital-nameplate',
            idta_version: '3.0.1',
            semantic_id: 'urn:sm',
            source_metadata: { resolved_version: '3.0.1', source_repo_ref: 'main', source_url: 'https://example.test' },
            definition: {
              submodel: {
                idShort: 'Nameplate',
                elements: [{ modelType: 'Property', idShort: 'ManufacturerName', valueType: 'xs:string' }],
              },
            },
            schema: { type: 'object', properties: { ManufacturerName: { type: 'string' } } },
            unsupported_nodes: [],
          }),
        );
      }
      return Promise.resolve(okJson({}));
    });

    tenantApiFetchMock.mockResolvedValue(
      okJson({
        id: 'dpp-1',
        status: 'draft',
        access: { can_read: true, can_update: true, can_publish: true, can_archive: true },
        aas_environment: { submodels: [{ id: 'urn:sm:1', idShort: 'Nameplate', semanticId: { keys: [{ value: 'urn:sm' }] } }] },
        submodel_bindings: [{ template_key: 'digital-nameplate', submodel_id: 'urn:sm:1', semantic_id: 'urn:sm' }],
      }),
    );
  });

  it('still renders editor route after shared shell extraction', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={['/console/dpps/dpp-1/edit/digital-nameplate']}>
          <Routes>
            <Route path="/console/dpps/:dppId/edit/:templateKey" element={<SubmodelEditorPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText(/Submodel Data/i)).toBeTruthy();
    });
  });
});
