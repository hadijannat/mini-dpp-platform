// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { EPCISEvent } from '@/features/epcis/lib/epcisApi';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockEvents: EPCISEvent[] = [
  {
    id: 'evt-1',
    dpp_id: 'dpp-aaa-bbb',
    event_id: 'urn:uuid:event-1',
    event_type: 'ObjectEvent',
    event_time: '2026-02-07T10:00:00Z',
    event_time_zone_offset: '+01:00',
    action: 'OBSERVE',
    biz_step: 'shipping',
    disposition: 'in_transit',
    read_point: null,
    biz_location: null,
    payload: {},
    error_declaration: null,
    created_by_subject: 'test',
    created_at: '2026-02-07T10:00:00Z',
  },
  {
    id: 'evt-2',
    dpp_id: 'dpp-aaa-bbb',
    event_id: 'urn:uuid:event-2',
    event_type: 'AggregationEvent',
    event_time: '2026-02-07T11:00:00Z',
    event_time_zone_offset: '+01:00',
    action: 'ADD',
    biz_step: 'packing',
    disposition: 'active',
    read_point: null,
    biz_location: null,
    payload: {},
    error_declaration: null,
    created_by_subject: 'test',
    created_at: '2026-02-07T11:00:00Z',
  },
];

vi.mock('react-oidc-context', () => ({
  useAuth: () => ({
    user: { access_token: 'fake-token' },
    isAuthenticated: true,
    signinRedirect: vi.fn(),
  }),
}));

vi.mock('@/lib/tenant', () => ({
  getTenantSlug: () => 'default',
}));

let epcisResponse: { eventList: EPCISEvent[] } = { eventList: [] };
let dppsResponse = { count: 0, dpps: [] as unknown[] };

vi.mock('@/features/epcis/lib/epcisApi', async () => {
  const actual = await vi.importActual<typeof import('@/features/epcis/lib/epcisApi')>(
    '@/features/epcis/lib/epcisApi',
  );
  return {
    ...actual,
    fetchEPCISEvents: vi.fn(() => Promise.resolve(epcisResponse)),
  };
});

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ count: 0, templates: [] }),
    }),
  ),
  tenantApiFetch: vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(dppsResponse),
    }),
  ),
  getApiErrorMessage: vi.fn(() => Promise.resolve('Error')),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const { default: DashboardPage } = await import('../pages/DashboardPage');

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DashboardPage — EPCIS section', () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    epcisResponse = { eventList: [] };
    dppsResponse = { count: 0, dpps: [] };
  });

  it('renders "Supply Chain Events" stat card with event count', async () => {
    epcisResponse = { eventList: mockEvents };

    await renderDashboard();

    // Wait for the query to resolve and the count to update
    expect(await screen.findByText('Supply Chain Events')).toBeTruthy();
    // The count renders as 2 after the EPCIS query resolves
    await waitFor(() => {
      expect(screen.getByText('2')).toBeTruthy();
    });
  });

  it('renders recent events table with event type and bizStep', async () => {
    epcisResponse = { eventList: mockEvents };

    await renderDashboard();

    // Wait for the table to appear (only rendered after query resolves with events)
    expect(await screen.findByText('Recent Supply Chain Events')).toBeTruthy();

    // Event type badges should render
    expect(screen.getByText('ObjectEvent')).toBeTruthy();
    expect(screen.getByText('AggregationEvent')).toBeTruthy();

    // Business step values should render
    expect(screen.getByText('shipping')).toBeTruthy();
    expect(screen.getByText('packing')).toBeTruthy();
  });

  it('does not render recent events section when no events', async () => {
    epcisResponse = { eventList: [] };

    await renderDashboard();

    // Wait for queries to settle: the "Dashboard" heading is always rendered
    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeTruthy();
    });

    // The stat card "Supply Chain Events" is still rendered (with value 0)
    expect(screen.getByText('Supply Chain Events')).toBeTruthy();

    // But the recent events table heading should NOT be present
    expect(screen.queryByText('Recent Supply Chain Events')).toBeNull();
  });
});
