// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import SubmodelEditorPage from '../SubmodelEditorPage';

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

function renderEditor(
  initialEntry = '/console/dpps/dpp-1/edit/digital-nameplate',
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/console/dpps/:dppId/edit/:templateKey" element={<SubmodelEditorPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const dppResponse = {
  id: 'dpp-1',
  status: 'draft',
  access: {
    can_read: true,
    can_update: true,
    can_publish: true,
    can_archive: true,
    source: 'owner',
  },
  aas_environment: {
    submodels: [
      {
        id: 'urn:submodel:nameplate',
        idShort: 'Nameplate',
        semanticId: { keys: [{ value: 'urn:semantic:digital-nameplate' }] },
        submodelElements: [],
      },
    ],
  },
  submodel_bindings: [
    {
      template_key: 'digital-nameplate',
      submodel_id: 'urn:submodel:nameplate',
      semantic_id: 'urn:semantic:digital-nameplate',
      binding_source: 'semantic_exact',
    },
  ],
};

const templateContract = {
  template_key: 'digital-nameplate',
  idta_version: '3.0.1',
  semantic_id: 'urn:semantic:digital-nameplate',
  source_metadata: {
    resolved_version: '3.0.1',
    source_repo_ref: 'main',
    source_url: 'https://example.com',
  },
  definition: {
    submodel: {
      idShort: 'Nameplate',
      elements: [
        {
          modelType: 'SubmodelElementCollection',
          idShort: 'ManufacturerData',
          children: [
            {
              modelType: 'Property',
              idShort: 'ManufacturerName',
              smt: { cardinality: 'One' },
            },
          ],
        },
      ],
    },
  },
  schema: {
    type: 'object',
    properties: {
      ManufacturerData: {
        type: 'object',
        properties: {
          ManufacturerName: {
            type: 'string',
          },
        },
      },
    },
  },
};

describe('SubmodelEditorPage progress and rebuild strategy', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    if (!('scrollIntoView' in HTMLElement.prototype)) {
      Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
        configurable: true,
        value: vi.fn(),
      });
    } else {
      vi.spyOn(HTMLElement.prototype, 'scrollIntoView').mockImplementation(() => {});
    }

    apiFetchMock.mockImplementation((path: string) => {
      if (path === '/api/v1/templates/digital-nameplate') {
        return Promise.resolve(
          okJson({
            template_key: 'digital-nameplate',
            semantic_id: 'urn:semantic:digital-nameplate',
          }),
        );
      }
      if (path === '/api/v1/templates/digital-nameplate/contract') {
        return Promise.resolve(okJson(templateContract));
      }
      return Promise.resolve(okJson({}));
    });

    tenantApiFetchMock.mockImplementation((path: string, options?: { method?: string }) => {
      if (path === '/dpps/dpp-1') {
        return Promise.resolve(okJson(dppResponse));
      }
      if (path === '/dpps/dpp-1/submodel' && options?.method === 'PUT') {
        return Promise.resolve(okJson({ id: 'rev-1', revision_no: 2, state: 'draft' }));
      }
      return Promise.resolve(okJson({}));
    });
  });

  it(
    'renders section progress and opens destructive rebuild confirmation dialog',
    async () => {
    renderEditor();

    await waitFor(() => {
      expect(screen.getByText(/Section Progress/i)).toBeTruthy();
    });

    expect(screen.getAllByText(/ManufacturerData/i).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /rebuild from template/i }));

    await waitFor(() => {
      expect(screen.getByText(/Rebuild submodel from template\?/i)).toBeTruthy();
    });

    expect(screen.getByRole('button', { name: /confirm rebuild/i })).toBeTruthy();
    },
    15000,
  );

  it(
    'sends bound submodel_id in update requests',
    async () => {
      renderEditor();

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /rebuild from template/i })).toBeTruthy();
      });

      fireEvent.click(screen.getByRole('button', { name: /rebuild from template/i }));
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /confirm rebuild/i })).toBeTruthy();
      });
      fireEvent.click(screen.getByRole('button', { name: /confirm rebuild/i }));

      await waitFor(() => {
        const updateCall = tenantApiFetchMock.mock.calls.find(
          (call) => call[0] === '/dpps/dpp-1/submodel' && call[1]?.method === 'PUT',
        );
        expect(updateCall).toBeTruthy();
        const body = String(updateCall?.[1]?.body ?? '{}');
        const payload = JSON.parse(body) as Record<string, unknown>;
        expect(payload.submodel_id).toBe('urn:submodel:nameplate');
      });
    },
    15000,
  );

  it(
    'renders outline pane and applies focus from focus_path query params',
    async () => {
      renderEditor(
        '/console/dpps/dpp-1/edit/digital-nameplate?focus_path=ManufacturerData.ManufacturerName',
      );

      await waitFor(() => {
        expect(screen.getByTestId('dpp-outline-submodel-desktop')).toBeTruthy();
      });

      const target = document.querySelector<HTMLElement>(
        '[data-field-path="ManufacturerData.ManufacturerName"]',
      );
      expect(target).toBeTruthy();

      await waitFor(() => {
        const scrolled = (HTMLElement.prototype.scrollIntoView as unknown as ReturnType<typeof vi.fn>);
        expect(scrolled).toHaveBeenCalled();
      });

      expect(screen.queryByText(/Could not focus requested field/i)).toBeNull();
    },
    15000,
  );
});
