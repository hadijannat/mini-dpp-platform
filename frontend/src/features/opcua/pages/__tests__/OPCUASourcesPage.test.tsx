// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('react-oidc-context', () => ({
  useAuth: () => ({
    user: { access_token: 'fake-token', profile: { realm_access: { roles: ['publisher'] } } },
    isAuthenticated: true,
    signinRedirect: vi.fn(),
  }),
}));

vi.mock('@/lib/tenant', () => ({
  getTenantSlug: () => 'default',
}));

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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const { default: OPCUAPage } = await import('../OPCUAPage');

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/console/opcua#sources']}>
        <OPCUAPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('OPCUAPage — Sources tab', () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    mockApiResponse = { items: [], total: 0 };
    mockApiStatus = 200;
  });

  it('renders page header and tabs', async () => {
    await renderPage();
    expect(await screen.findByText('OPC UA')).toBeTruthy();
    expect(screen.getByText('Sources')).toBeTruthy();
    expect(screen.getByText('NodeSets')).toBeTruthy();
    expect(screen.getByText('Mappings')).toBeTruthy();
    expect(screen.getByText('Dataspace')).toBeTruthy();
  });

  it('renders empty state when no sources exist', async () => {
    await renderPage();
    expect(await screen.findByText('No OPC UA sources')).toBeTruthy();
    expect(screen.getByText(/Add a source to start ingesting/)).toBeTruthy();
  });

  it('renders sources table when data exists', async () => {
    mockApiResponse = {
      items: [
        {
          id: '1',
          tenant_id: 't1',
          name: 'Test PLC',
          endpoint_url: 'opc.tcp://192.168.1.100:4840',
          auth_type: 'anonymous',
          connection_status: 'healthy',
          has_password: false,
          username: null,
          security_policy: null,
          security_mode: null,
          client_cert_ref: null,
          client_key_ref: null,
          server_cert_pinned_sha256: null,
          last_seen_at: new Date().toISOString(),
          created_by: 'user',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
    };

    await renderPage();
    expect(await screen.findByText('Test PLC')).toBeTruthy();
    expect(screen.getByText('opc.tcp://192.168.1.100:4840')).toBeTruthy();
    expect(screen.getByText('Anonymous')).toBeTruthy();
    expect(screen.getByText('Connected')).toBeTruthy();
  });

  it('renders feature disabled banner on 410 response', async () => {
    mockApiStatus = 410;

    await renderPage();

    await waitFor(() => {
      expect(screen.getByText(/OPC UA integration is not enabled/)).toBeTruthy();
    });
  });
});
