// @vitest-environment jsdom
import { describe, expect, it, beforeEach, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import DPPViewerPage from '../DPPViewerPage';

vi.mock('react-oidc-context', () => ({
  useAuth: () => ({ isAuthenticated: false, user: null }),
}));

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
  tenantApiFetch: vi.fn(),
  getApiErrorMessage: vi.fn().mockResolvedValue('Failed to fetch DPP'),
}));

vi.mock('@/features/epcis/lib/epcisApi', () => ({
  fetchPublicEPCISEvents: vi.fn().mockResolvedValue({ eventList: [] }),
}));

import { apiFetch } from '@/lib/api';

const mockDppResponse = {
  id: '8f706ac0-8a2e-48be-8f53-58c477f3079d',
  status: 'PUBLISHED',
  asset_ids: {
    manufacturerPartId: 'MP-100',
  },
  created_at: '2026-02-09T00:00:00Z',
  updated_at: '2026-02-09T00:00:00Z',
  current_revision_no: 1,
  aas_environment: {
    submodels: [
      {
        id: 'urn:sm:nameplate',
        idShort: 'Nameplate',
        submodelElements: [
          {
            modelType: 'Property',
            idShort: 'ManufacturerName',
            value: 'ACME',
          },
        ],
      },
      {
        id: 'urn:sm:carbon',
        idShort: 'CarbonFootprint',
        submodelElements: [
          {
            modelType: 'Property',
            idShort: 'TotalCO2',
            value: '42kg',
          },
        ],
      },
    ],
  },
  digest_sha256: null,
};

let scrollIntoViewMock = vi.fn();

function renderViewer(initialPath: string, routePath: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path={routePath} element={<DPPViewerPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('DPPViewerPage', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    scrollIntoViewMock = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoViewMock,
    });
    (apiFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDppResponse),
    });
  });

  it('fetches published DPP via public endpoint by ID', async () => {
    renderViewer('/t/acme/dpp/abc-123', '/t/:tenantSlug/dpp/:dppId');

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/public/acme/dpps/abc-123');
    });
  });

  it('fetches published DPP via public endpoint by slug', async () => {
    renderViewer('/t/acme/p/deadbeef', '/t/:tenantSlug/p/:slug');

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/public/acme/dpps/slug/deadbeef');
    });
  });

  it('renders outline and switches category tab + scroll target on node click', async () => {
    renderViewer('/t/acme/dpp/abc-123', '/t/:tenantSlug/dpp/:dppId');

    const outlinePane = await waitFor(() => screen.getByTestId('dpp-outline-viewer-desktop'));

    fireEvent.click(within(outlinePane).getByRole('treeitem', { name: /TotalCO2/i }));

    await waitFor(() => {
      const environmentalTab = screen.getByRole('tab', { name: /Environmental Impact/i });
      expect(environmentalTab.getAttribute('data-state')).toBe('active');
    });

    await waitFor(() => {
      expect(scrollIntoViewMock).toHaveBeenCalled();
    });
  });
});
