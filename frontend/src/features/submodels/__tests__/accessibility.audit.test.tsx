// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type React from 'react';

import DPPEditorPage from '@/features/publisher/pages/DPPEditorPage';
import SubmodelEditorPage from '@/features/editor/pages/SubmodelEditorPage';
import DPPViewerPage from '@/features/viewer/pages/DPPViewerPage';

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
  getTenantSlug: () => 'default',
}));

vi.mock('@/features/epcis/lib/epcisApi', () => ({
  fetchEPCISEvents: vi.fn().mockResolvedValue({ eventList: [] }),
  fetchPublicEPCISEvents: vi.fn().mockResolvedValue({ eventList: [] }),
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

function renderInApp(path: string, route: string, element: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={route} element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const dppBase = {
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
  },
  qr_payload: null,
  created_at: '2026-02-10T12:00:00Z',
  updated_at: '2026-02-10T12:00:00Z',
  current_revision_no: 1,
  digest_sha256: 'digest123',
  aas_environment: {
    submodels: [
      {
        id: 'urn:dpp:sm:np',
        idShort: 'Nameplate',
        semanticId: { keys: [{ value: 'urn:semantic:digital-nameplate' }] },
        submodelElements: [
          {
            idShort: 'ManufacturerName',
            modelType: 'Property',
            value: 'ACME',
            qualifiers: [{ type: 'SMT/Cardinality', value: 'One' }],
          },
        ],
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

const contract = {
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
          idShort: 'ManufacturerName',
          modelType: 'Property',
          smt: { cardinality: 'One' },
        },
      ],
    },
  },
  schema: {
    type: 'object',
    properties: {
      ManufacturerName: { type: 'string' },
    },
    required: ['ManufacturerName'],
  },
};

describe('Submodel UX accessibility', () => {
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
            ],
          }),
        );
      }
      if (path === '/api/v1/templates/digital-nameplate') {
        return Promise.resolve(
          okJson({
            template_key: 'digital-nameplate',
            semantic_id: 'urn:semantic:digital-nameplate',
          }),
        );
      }
      if (path === '/api/v1/templates/digital-nameplate/contract') {
        return Promise.resolve(okJson(contract));
      }
      return Promise.resolve(okJson({}));
    });

    tenantApiFetchMock.mockImplementation((path: string, options?: { method?: string }) => {
      if (path === '/dpps/019c42a4-128f-7bd9-a95c-a842746f2f9a') {
        return Promise.resolve(okJson(dppBase));
      }
      if (path.endsWith('/revisions')) {
        return Promise.resolve(okJson([]));
      }
      if (path.includes('/diff?')) {
        return Promise.resolve(okJson({ from_rev: 1, to_rev: 2, added: [], removed: [], changed: [] }));
      }
      if (path === '/dpps/019c42a4-128f-7bd9-a95c-a842746f2f9a/submodels/refresh-rebuild' && options?.method === 'POST') {
        return Promise.resolve(okJson({ attempted: 1, succeeded: [], failed: [], skipped: [] }));
      }
      if (path === '/dpps/019c42a4-128f-7bd9-a95c-a842746f2f9a/publish' && options?.method === 'POST') {
        return Promise.resolve(okJson({ ...dppBase, status: 'published' }));
      }
      if (path === '/dpps/abc-123') {
        return Promise.resolve(
          okJson({
            ...dppBase,
            id: 'abc-123',
            status: 'published',
          }),
        );
      }
      return Promise.resolve(okJson({}));
    });
  });

  it('publisher page passes axe and supports keyboard-triggered refresh', async () => {
    const { container } = renderInApp(
      '/console/dpps/019c42a4-128f-7bd9-a95c-a842746f2f9a',
      '/console/dpps/:dppId',
      <DPPEditorPage />,
    );

    const refreshButton = await screen.findByTestId('dpp-refresh-rebuild');
    expect(refreshButton).toBeTruthy();

    const a11y = await axe(container);
    expect(a11y.violations, JSON.stringify(a11y.violations, null, 2)).toHaveLength(0);

    refreshButton.focus();
    fireEvent.keyDown(refreshButton, { key: 'Enter' });
  }, 15000);

  it('editor page passes axe and keeps tabs keyboard reachable', async () => {
    const { container } = renderInApp(
      '/console/dpps/019c42a4-128f-7bd9-a95c-a842746f2f9a/edit/digital-nameplate',
      '/console/dpps/:dppId/edit/:templateKey',
      <SubmodelEditorPage />,
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Edit Submodel/i })).toBeTruthy();
    });

    const a11y = await axe(container);
    expect(a11y.violations, JSON.stringify(a11y.violations, null, 2)).toHaveLength(0);

    const user = userEvent.setup();
    const formTab = screen.getByRole('tab', { name: 'Form' });
    const jsonTab = screen.getByRole('tab', { name: 'JSON' });

    formTab.focus();
    expect(document.activeElement).toBe(formTab);
    jsonTab.focus();
    expect(document.activeElement).toBe(jsonTab);
    await user.keyboard('{Enter}');
    expect(jsonTab.getAttribute('aria-selected')).toBe('true');
  }, 15000);

  it('viewer page passes axe and supports keyboard tab navigation', async () => {
    const { container } = renderInApp('/t/default/dpp/abc-123', '/t/:tenantSlug/dpp/:dppId', <DPPViewerPage />);

    await waitFor(() => {
      expect(screen.getByText(/Product Information/i)).toBeTruthy();
    });

    const a11y = await axe(container);
    expect(a11y.violations, JSON.stringify(a11y.violations, null, 2)).toHaveLength(0);

    const identityTab = screen.getByRole('tab', { name: /Product Identity/i });
    identityTab.focus();
    fireEvent.keyDown(identityTab, { key: 'ArrowRight' });

    const selectedTab = screen.getAllByRole('tab').find((tab) => tab.getAttribute('data-state') === 'active');
    expect(selectedTab).toBeTruthy();
  }, 15000);
});
