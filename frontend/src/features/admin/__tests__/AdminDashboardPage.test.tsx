// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

// Mock react-oidc-context
vi.mock('react-oidc-context', () => ({
  useAuth: () => ({
    user: { access_token: 'test-token' },
    isAuthenticated: true,
    signinRedirect: vi.fn(),
  }),
}));

// Mock apiFetch
vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
  getApiErrorMessage: vi.fn().mockResolvedValue('Error'),
}));

import { apiFetch } from '@/lib/api';
import AdminDashboardPage from '../pages/AdminDashboardPage';

const mockMetrics = {
  tenants: [
    {
      tenant_id: '123',
      slug: 'acme',
      name: 'Acme Corp',
      status: 'active',
      total_dpps: 12,
      draft_dpps: 4,
      published_dpps: 6,
      archived_dpps: 2,
      total_revisions: 30,
      total_members: 5,
      total_epcis_events: 15,
      total_data_carriers: 8,
      active_data_carriers: 6,
      withdrawn_data_carriers: 2,
      system_managed_resolver_links: 11,
      total_audit_events: 50,
    },
  ],
  totals: {
    total_tenants: 1,
    total_dpps: 12,
    total_published: 6,
    total_members: 5,
    total_epcis_events: 15,
    total_data_carriers: 8,
    total_active_data_carriers: 6,
    total_withdrawn_data_carriers: 2,
    total_system_managed_resolver_links: 11,
    total_audit_events: 50,
  },
};

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('AdminDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders overview cards with totals', async () => {
    (apiFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockMetrics),
    });

    renderWithProviders(<AdminDashboardPage />);

    // Wait for data to load
    expect(await screen.findByText('Admin Dashboard')).toBeTruthy();
    // Values appear in both overview cards and table, so use getAllByText
    expect(screen.getAllByText('12').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('6').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('5').length).toBeGreaterThanOrEqual(1);
    // Check overview card labels are present
    expect(screen.getByText('Total DPPs')).toBeTruthy();
    // "Published" and "Members" also appear as table headers
    expect(screen.getAllByText('Published').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Members').length).toBeGreaterThanOrEqual(1);
  });

  it('renders per-tenant table', async () => {
    (apiFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockMetrics),
    });

    renderWithProviders(<AdminDashboardPage />);

    expect(await screen.findByText('Acme Corp')).toBeTruthy();
    expect(screen.getByText('acme')).toBeTruthy();
    expect(screen.getByText('active')).toBeTruthy();
  });

  it('shows error banner on fetch failure', async () => {
    (apiFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: 'Forbidden' }),
      text: () => Promise.resolve('Forbidden'),
    });

    renderWithProviders(<AdminDashboardPage />);

    expect(await screen.findByText(/Error/i)).toBeTruthy();
  });

  it('renders empty state when no tenants', async () => {
    (apiFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          tenants: [],
          totals: {
            total_tenants: 0,
            total_dpps: 0,
            total_published: 0,
            total_members: 0,
            total_epcis_events: 0,
            total_data_carriers: 0,
            total_active_data_carriers: 0,
            total_withdrawn_data_carriers: 0,
            total_system_managed_resolver_links: 0,
            total_audit_events: 0,
          },
        }),
    });

    renderWithProviders(<AdminDashboardPage />);

    expect(await screen.findByText('No tenants found.')).toBeTruthy();
  });
});
