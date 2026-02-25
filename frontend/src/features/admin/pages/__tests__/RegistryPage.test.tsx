// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
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
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
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
  beforeEach(async () => {
    mockDescriptors = [];
    // Reset tenantApiFetch to the default implementation
    const { tenantApiFetch } = await import('@/lib/api');
    const mockFetch = tenantApiFetch as ReturnType<typeof vi.fn>;
    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockDescriptors),
      }),
    );
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

  it('shows error banner when API returns error', async () => {
    const { tenantApiFetch } = await import('@/lib/api');
    const mockFetch = tenantApiFetch as ReturnType<typeof vi.fn>;
    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: false,
        status: 500,
        headers: new Headers({ 'content-type': 'text/plain' }),
        text: () => Promise.resolve('Internal Server Error'),
      }),
    );

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const { default: RegistryPage } = await import('../RegistryPage');

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <RegistryPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // The ErrorBanner renders the message from getApiErrorMessage which returns 'Error'
    await waitFor(() => {
      expect(screen.getByText(/Failed to load|Error/)).toBeTruthy();
    });
  });

  it('expands row when clicked to show details', async () => {
    mockDescriptors = [
      {
        id: 'desc-1',
        tenant_id: 'tenant-1',
        aas_id: 'urn:example:aas:expand',
        id_short: 'ExpandShell',
        global_asset_id: 'urn:example:asset:expand',
        specific_asset_ids: [{ name: 'partId', value: 'ABC-123' }],
        submodel_descriptors: [
          { id: 'sm-1', idShort: 'TechData', semanticId: { keys: [{ value: 'urn:sem:1' }] } },
        ],
        dpp_id: null,
        created_by_subject: 'admin',
        created_at: '2026-02-08T10:00:00Z',
        updated_at: '2026-02-08T10:00:00Z',
      },
    ];

    await renderPage();

    // Wait for data to load
    const aasIdCell = await screen.findByText('urn:example:aas:expand');
    expect(aasIdCell).toBeTruthy();

    // Click the row to expand
    const row = aasIdCell.closest('tr');
    if (row) {
      fireEvent.click(row);
    }

    // After expansion, should show the specific asset IDs and submodel details
    await waitFor(() => {
      expect(screen.getByText('Specific Asset IDs')).toBeTruthy();
    });
    expect(screen.getByText(/partId.*ABC-123|ABC-123/)).toBeTruthy();
    expect(screen.getByText('Submodel Descriptors (1)')).toBeTruthy();
  });
});
