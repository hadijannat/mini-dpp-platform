// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

type TenantRole = 'viewer' | 'publisher' | 'tenant_admin' | 'admin';

const authState: {
  isAuthenticated: boolean;
  user: Record<string, unknown> | null;
} = {
  isAuthenticated: true,
  user: { profile: { roles: ['viewer'] } },
};

const tenantAccessState: {
  tenantSlug: string;
  role: TenantRole | null;
  isLoading: boolean;
  isError: boolean;
} = {
  tenantSlug: 'default',
  role: 'viewer',
  isLoading: false,
  isError: false,
};

const roleRank: Record<TenantRole, number> = {
  viewer: 0,
  publisher: 1,
  tenant_admin: 2,
  admin: 3,
};

function hasTenantRoleLevel(requiredRole: TenantRole): boolean {
  if (tenantAccessState.isLoading || tenantAccessState.isError || !tenantAccessState.role) {
    return false;
  }
  return roleRank[tenantAccessState.role] >= roleRank[requiredRole];
}

vi.mock('react-oidc-context', () => ({
  useAuth: () => authState,
}));

vi.mock('@/lib/tenant-access', () => ({
  useTenantAccess: () => ({
    tenantSlug: tenantAccessState.tenantSlug,
    activeTenantRole: tenantAccessState.role,
    hasTenantRoleLevel,
    isLoading: tenantAccessState.isLoading,
    isError: tenantAccessState.isError,
  }),
}));

import ProtectedRoute from '../ProtectedRoute';

function WelcomeProbe() {
  const location = useLocation();
  return <div>Welcome Page {location.search}</div>;
}

function renderRoutes(initialEntry: string = '/console') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route
          path="/console"
          element={
            <ProtectedRoute requiredRole="publisher">
              <div>Console</div>
            </ProtectedRoute>
          }
        />
        <Route
          path="/console/dpps/:dppId"
          element={
            <ProtectedRoute requiredRole="publisher">
              <div>DPP Detail</div>
            </ProtectedRoute>
          }
        />
        <Route
          path="/console/tenant"
          element={
            <ProtectedRoute requiredRole="publisher" roleSource="tenant">
              <div>Tenant Console</div>
            </ProtectedRoute>
          }
        />
        <Route path="/welcome" element={<WelcomeProbe />} />
        <Route path="/" element={<div>Landing</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    cleanup();
    sessionStorage.clear();
    authState.isAuthenticated = true;
    authState.user = { profile: { roles: ['viewer'] } };
    tenantAccessState.tenantSlug = 'default';
    tenantAccessState.role = 'viewer';
    tenantAccessState.isLoading = false;
    tenantAccessState.isError = false;
  });

  it('redirects authenticated viewers to welcome for publisher-only token routes', async () => {
    renderRoutes('/console');

    expect(await screen.findByText(/Welcome Page/)).toBeTruthy();
    expect(screen.queryByText('Console')).toBeNull();
    expect(screen.getByText(/reason=insufficient_role/)).toBeTruthy();
    expect(screen.getByText(/next=%2Fconsole/)).toBeTruthy();
  });

  it('allows viewers to access read-only DPP detail console route', async () => {
    renderRoutes('/console/dpps/019c42a4-128f-7bd9-a95c-a842746f2f9a');

    expect(await screen.findByText('DPP Detail')).toBeTruthy();
    expect(screen.queryByText(/Welcome Page/)).toBeNull();
  });

  it('redirects unauthenticated users to landing and stores intended route', async () => {
    authState.isAuthenticated = false;
    authState.user = null;

    renderRoutes('/console');

    expect(await screen.findByText('Landing')).toBeTruthy();
    expect(sessionStorage.getItem('auth.redirectUrl')).toBe('/console');
  });

  it('renders access denied if user does not have viewer-level token access', async () => {
    authState.isAuthenticated = true;
    authState.user = { profile: { roles: [] } };

    renderRoutes('/console');

    expect(await screen.findByText('Access Denied')).toBeTruthy();
    expect(screen.queryByText('Welcome Page')).toBeNull();
  });

  it('allows publisher access when tenant role source grants publisher in active tenant', async () => {
    tenantAccessState.role = 'publisher';

    renderRoutes('/console/tenant');

    expect(await screen.findByText('Tenant Console')).toBeTruthy();
    expect(screen.queryByText(/Welcome Page/)).toBeNull();
  });

  it('redirects to welcome with tenant and next when active tenant role is viewer', async () => {
    tenantAccessState.role = 'viewer';

    renderRoutes('/console/tenant');

    expect(await screen.findByText(/Welcome Page/)).toBeTruthy();
    expect(screen.queryByText('Tenant Console')).toBeNull();
    expect(screen.getByText(/reason=insufficient_role/)).toBeTruthy();
    expect(screen.getByText(/tenant=default/)).toBeTruthy();
    expect(screen.getByText(/next=%2Fconsole%2Ftenant/)).toBeTruthy();
  });

  it('fails closed when tenant membership lookup fails', async () => {
    tenantAccessState.role = 'tenant_admin';
    tenantAccessState.isError = true;

    renderRoutes('/console/tenant');

    expect(await screen.findByText('Access Denied')).toBeTruthy();
    expect(screen.queryByText('Tenant Console')).toBeNull();
  });
});
