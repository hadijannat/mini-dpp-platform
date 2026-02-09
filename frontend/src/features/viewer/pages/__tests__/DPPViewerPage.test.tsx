// @vitest-environment jsdom
import { describe, expect, it, beforeEach, vi } from 'vitest';
import { cleanup, render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import DPPViewerPage from '../DPPViewerPage';

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
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
  aas_environment: { submodels: [] },
  digest_sha256: null,
};

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
});
