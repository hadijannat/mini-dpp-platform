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

let mockWebhooks: unknown[] = [];

vi.mock('@/lib/api', () => ({
  tenantApiFetch: vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(mockWebhooks),
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
  const { default: WebhooksPage } = await import('../pages/WebhooksPage');

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <WebhooksPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('WebhooksPage', () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    mockWebhooks = [];
  });

  it('renders page header after loading', async () => {
    await renderPage();
    // Wait for query to resolve and loading spinner to disappear
    expect(await screen.findByText('Webhooks')).toBeTruthy();
    expect(screen.getByText('Add Webhook')).toBeTruthy();
  });

  it('shows empty state when no webhooks', async () => {
    await renderPage();
    expect(await screen.findByText('No webhooks configured')).toBeTruthy();
  });

  it('renders webhook cards when data exists', async () => {
    mockWebhooks = [
      {
        id: 'wh-1',
        url: 'https://example.com/hook',
        events: ['DPP_CREATED', 'DPP_PUBLISHED'],
        active: true,
        created_by_subject: 'admin',
        created_at: '2026-02-08T10:00:00Z',
        updated_at: '2026-02-08T10:00:00Z',
      },
    ];

    await renderPage();
    expect(await screen.findByText('https://example.com/hook')).toBeTruthy();
    expect(screen.getByText('DPP_CREATED')).toBeTruthy();
    expect(screen.getByText('DPP_PUBLISHED')).toBeTruthy();
    expect(screen.getByText('Active')).toBeTruthy();
  });

  it('opens create dialog when Add Webhook is clicked', async () => {
    await renderPage();
    // Wait for page to fully load
    const addButton = await screen.findByText('Add Webhook');
    fireEvent.click(addButton);
    await waitFor(() => {
      expect(screen.getByLabelText('URL')).toBeTruthy();
    });
    expect(screen.getByText('Create Webhook')).toBeTruthy();
  });
});
