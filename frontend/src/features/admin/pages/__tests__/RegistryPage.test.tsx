// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('react-oidc-context', () => ({
  useAuth: () => ({
    user: { access_token: 'fake-token', profile: { realm_access: { roles: ['admin'] } } },
    isAuthenticated: true,
    signinRedirect: vi.fn(),
  }),
}));

vi.mock('@/lib/tenant', () => ({
  getTenantSlug: () => 'default',
}));

let mockDescriptors: unknown[] = [];

vi.mock('@/lib/api', () => ({
  tenantApiFetch: vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(mockDescriptors),
    }),
  ),
  getApiErrorMessage: vi.fn(() => Promise.resolve('Error')),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const { default: RegistryPage } = await import('../RegistryPage');

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <RegistryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('RegistryPage', () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    mockDescriptors = [];
  });

  it('renders page header after loading', async () => {
    await renderPage();
    expect(await screen.findByText('Registry')).toBeTruthy();
  });

  it('shows empty state when no descriptors exist', async () => {
    await renderPage();
    expect(await screen.findByText('No shell descriptors')).toBeTruthy();
  });

  it('renders descriptors table when data exists', async () => {
    mockDescriptors = [
      {
        id: 'desc-1',
        tenant_id: 'tenant-1',
        aas_id: 'urn:example:aas:1',
        id_short: 'MyShell',
        global_asset_id: 'urn:example:asset:1',
        specific_asset_ids: [],
        submodel_descriptors: [
          { id: 'sm-1', idShort: 'TechnicalData', semanticId: { keys: [{ value: 'urn:sem:1' }] } },
        ],
        dpp_id: null,
        created_by_subject: 'admin',
        created_at: '2026-02-08T10:00:00Z',
        updated_at: '2026-02-08T10:00:00Z',
      },
    ];

    await renderPage();
    expect(await screen.findByText('urn:example:aas:1')).toBeTruthy();
    expect(screen.getByText('MyShell')).toBeTruthy();
    expect(screen.getByText('urn:example:asset:1')).toBeTruthy();
  });

  it('shows search and discovery panels', async () => {
    await renderPage();
    expect(await screen.findByText('Search by Asset ID')).toBeTruthy();
    expect(screen.getByText('Discovery Lookup')).toBeTruthy();
  });
});
