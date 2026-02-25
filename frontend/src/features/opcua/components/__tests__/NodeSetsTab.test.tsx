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
  const { NodeSetsTab } = await import('../NodeSetsTab');
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <NodeSetsTab />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('NodeSetsTab', () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    mockApiResponse = { items: [], total: 0 };
    mockApiStatus = 200;
  });

  it('renders empty state when no nodesets exist', async () => {
    await renderTab();
    expect(await screen.findByText(/No NodeSets uploaded/)).toBeTruthy();
  });

  it('renders Upload NodeSet button', async () => {
    await renderTab();
    expect(await screen.findByText('Upload NodeSet')).toBeTruthy();
  });

  it('renders nodesets table when data exists', async () => {
    mockApiResponse = {
      items: [
        {
          id: 'ns1',
          tenant_id: 't1',
          source_id: null,
          namespace_uri: 'http://opcfoundation.org/UA/DI/',
          nodeset_version: '1.0.4',
          publication_date: '2023-01-15',
          companion_spec_name: 'DI',
          companion_spec_version: '1.0.4',
          nodeset_file_ref: 'ref',
          companion_spec_file_ref: null,
          hash_sha256: 'abc',
          parsed_summary_json: { total_nodes: 142 },
          node_count: 142,
          created_by: 'user',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
    };

    await renderTab();
    expect(await screen.findByText('http://opcfoundation.org/UA/DI/')).toBeTruthy();
    expect(screen.getByText('1.0.4')).toBeTruthy();
  });

  it('renders feature disabled banner on 410 response', async () => {
    mockApiStatus = 410;
    await renderTab();
    await waitFor(() => {
      expect(screen.getByText(/OPC UA integration is not enabled/)).toBeTruthy();
    });
  });
});
