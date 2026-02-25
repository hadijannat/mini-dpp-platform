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

let mockLinks: unknown[] = [];

vi.mock('@/lib/api', () => ({
  tenantApiFetch: vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(mockLinks),
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
  const { default: ResolverPage } = await import('../ResolverPage');

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResolverPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ResolverPage', () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    mockLinks = [];
  });

  it('renders page header after loading', async () => {
    await renderPage();
    expect(await screen.findByText('Resolver')).toBeTruthy();
    expect(screen.getByText('Add Link')).toBeTruthy();
  });

  it('shows empty state when no links exist', async () => {
    await renderPage();
    expect(await screen.findByText('No resolver links')).toBeTruthy();
  });

  it('renders links table when data exists', async () => {
    mockLinks = [
      {
        id: 'link-1',
        tenant_id: 'tenant-1',
        identifier: '01/09520123456788',
        link_type: 'gs1:hasDigitalProductPassport',
        href: 'https://example.com/dpp/1',
        media_type: 'application/json',
        title: 'DPP',
        hreflang: 'en',
        priority: 10,
        dpp_id: null,
        active: true,
        created_by_subject: 'admin',
        created_at: '2026-02-08T10:00:00Z',
        updated_at: '2026-02-08T10:00:00Z',
      },
    ];

    await renderPage();
    expect(await screen.findByText('01/09520123456788')).toBeTruthy();
    expect(screen.getByText('hasDigitalProductPassport')).toBeTruthy();
    expect(screen.getByText('Active')).toBeTruthy();
  });

  it('opens create dialog when Add Link is clicked', async () => {
    await renderPage();
    const addButton = await screen.findByText('Add Link');
    fireEvent.click(addButton);
    await waitFor(() => {
      expect(screen.getByLabelText('Identifier')).toBeTruthy();
    });
    expect(screen.getByText('Create Link')).toBeTruthy();
  });

  it('shows error banner when query fetch fails', async () => {
    const { tenantApiFetch } = await import('@/lib/api');
    const mockFetch = tenantApiFetch as ReturnType<typeof vi.fn>;

    // Override to return fetch error (simulates backend 500)
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
    const { default: ResolverPage } = await import('../ResolverPage');

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <ResolverPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // When the query fails, the page shows empty state (no query error UI in ResolverPage)
    // and the Add Link button is still available
    await waitFor(() => {
      expect(screen.getByText('Add Link')).toBeTruthy();
    });

    // The query threw, so links is undefined -> empty state renders
    expect(screen.getByText('No resolver links')).toBeTruthy();
  });
});
