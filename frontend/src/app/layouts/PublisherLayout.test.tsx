// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

const authState = {
  user: {
    access_token: 'fake-token',
    profile: { roles: ['viewer'], sub: 'user-123' },
  },
  signoutRedirect: vi.fn(),
};
let opcuaEnabled = true;

vi.mock('react-oidc-context', () => ({
  useAuth: () => authState,
}));

vi.mock('@/lib/tenant', () => ({
  getTenantSlug: () => 'default',
}));

vi.mock('@/lib/breadcrumbs', () => ({
  useBreadcrumbs: () => [],
}));

vi.mock('@/features/opcua/lib/opcuaApi', () => ({
  fetchOpcuaFeatureStatus: vi.fn(() => Promise.resolve({ enabled: opcuaEnabled })),
}));

vi.mock('../components/SidebarNav', () => ({
  default: ({ navigation }: { navigation: Array<{ name: string }> }) => (
    <nav>
      {navigation.map((item) => (
        <span key={item.name}>{item.name}</span>
      ))}
    </nav>
  ),
}));

vi.mock('../components/SidebarUserFooter', () => ({
  default: () => <div>Sidebar footer</div>,
}));

import PublisherLayout from './PublisherLayout';

afterEach(() => {
  cleanup();
});

function renderLayout() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PublisherLayout />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PublisherLayout role request navigation', () => {
  beforeEach(() => {
    authState.user = {
      access_token: 'fake-token',
      profile: { roles: ['viewer'], sub: 'user-123' },
    };
    opcuaEnabled = true;
  });

  it('shows Role Requests for tenant_admin users', async () => {
    authState.user = {
      access_token: 'fake-token',
      profile: { roles: ['tenant_admin'], sub: 'user-123' },
    };
    renderLayout();

    expect(screen.queryAllByText('Role Requests').length).toBeGreaterThan(0);
    expect(screen.queryAllByText('Admin').length).toBe(0);
    expect((await screen.findAllByText('OPC UA')).length).toBeGreaterThan(0);
  });

  it('shows Role Requests and Admin navigation for platform admin users', async () => {
    authState.user = {
      access_token: 'fake-token',
      profile: { roles: ['admin'], sub: 'user-123' },
    };
    renderLayout();

    expect(screen.queryAllByText('Role Requests').length).toBeGreaterThan(0);
    expect(screen.queryAllByText('Admin').length).toBeGreaterThan(0);
    expect((await screen.findAllByText('OPC UA')).length).toBeGreaterThan(0);
  });
});

describe('PublisherLayout OPC UA nav gating', () => {
  beforeEach(() => {
    authState.user = {
      access_token: 'fake-token',
      profile: { roles: ['viewer'], sub: 'user-123' },
    };
  });

  it('hides OPC UA navigation when backend reports feature disabled', async () => {
    opcuaEnabled = false;

    renderLayout();

    await waitFor(() => {
      expect(screen.queryAllByText('OPC UA')).toHaveLength(0);
    });
  });

  it('shows OPC UA navigation when backend reports feature enabled', async () => {
    opcuaEnabled = true;

    renderLayout();

    expect((await screen.findAllByText('OPC UA')).length).toBeGreaterThan(0);
  });
});
