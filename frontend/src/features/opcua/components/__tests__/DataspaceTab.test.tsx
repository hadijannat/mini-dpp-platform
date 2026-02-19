// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

vi.mock('react-oidc-context', () => ({
  useAuth: () => ({
    user: { access_token: 'fake-token', profile: { realm_access: { roles: ['publisher'] } } },
    isAuthenticated: true,
  }),
}));

vi.mock('@/lib/tenant', () => ({ getTenantSlug: () => 'default' }));

let mockApiResponse: unknown = { items: [], total: 0 };
let mockApiStatus = 200;

vi.mock('@/lib/api', () => ({
  tenantApiFetch: vi.fn(() =>
    Promise.resolve({
      ok: mockApiStatus >= 200 && mockApiStatus < 300,
      status: mockApiStatus,
      json: () => Promise.resolve(mockApiResponse),
    }),
  ),
  getApiErrorMessage: vi.fn(() => Promise.resolve('API Error')),
}));

async function renderTab() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const { DataspaceTab } = await import('../DataspaceTab');
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DataspaceTab />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('DataspaceTab', () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    mockApiResponse = { items: [], total: 0 };
    mockApiStatus = 200;
  });

  it('renders empty state when no jobs exist', async () => {
    await renderTab();
    expect(await screen.findByText('No publication jobs')).toBeTruthy();
  });

  it('renders Publish to Dataspace button', async () => {
    await renderTab();
    expect(await screen.findByText('Publish to Dataspace')).toBeTruthy();
  });

  it('renders jobs table with status badges', async () => {
    mockApiResponse = {
      items: [
        {
          id: 'j1',
          tenant_id: 't1',
          dpp_id: 'dpp-123',
          status: 'succeeded',
          target: 'catena-x',
          artifact_refs: { dtr_id: 'abc' },
          error: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
    };

    await renderTab();
    expect(await screen.findByText('dpp-123')).toBeTruthy();
    expect(screen.getByText('catena-x')).toBeTruthy();
    expect(screen.getByText('Completed')).toBeTruthy();
  });

  it('shows retry button for failed jobs', async () => {
    mockApiResponse = {
      items: [
        {
          id: 'j2',
          tenant_id: 't1',
          dpp_id: 'dpp-456',
          status: 'failed',
          target: 'catena-x',
          artifact_refs: {},
          error: 'Connection timeout',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
    };

    await renderTab();
    expect(await screen.findByText('Failed')).toBeTruthy();
    expect(screen.getByText('Retry')).toBeTruthy();
  });

  it('renders feature disabled banner on 410', async () => {
    mockApiStatus = 410;
    await renderTab();
    await waitFor(() => {
      expect(screen.getByText(/OPC UA integration is not enabled/)).toBeTruthy();
    });
  });
});
