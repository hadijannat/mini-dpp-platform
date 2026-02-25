// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';

const authState = {
  isAuthenticated: true,
  isLoading: false,
  user: { profile: { roles: ['tenant_admin'] } },
};

const tenantAccessState = {
  tenantSlug: 'default',
  hasTenantRoleLevel: (
    requiredRole: 'viewer' | 'publisher' | 'tenant_admin' | 'admin',
  ): boolean =>
    requiredRole === 'viewer',
};

vi.mock('react-oidc-context', () => ({
  useAuth: () => authState,
}));

vi.mock('@/lib/tenant-access', () => ({
  useTenantAccess: () => ({
    tenantSlug: tenantAccessState.tenantSlug,
    activeTenantRole: null,
    hasTenantRoleLevel: tenantAccessState.hasTenantRoleLevel,
    isLoading: false,
    isError: false,
  }),
}));

vi.mock('./app/layouts/PublisherLayout', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  const Outlet = actual.Outlet;
  return {
    default: () => <Outlet />,
  };
});

vi.mock('./features/admin/pages/RoleRequestsPage', () => ({
  default: () => <div>Role Requests Page</div>,
}));

vi.mock('./features/onboarding/pages/WelcomePage', () => ({
  default: function WelcomeProbe() {
    const location = useLocation();
    return <div>Welcome Page {location.search}</div>;
  },
}));

import App from './App';

describe('App role requests route', () => {
  it('denies tenant-admin token users when active tenant role is viewer', async () => {
    authState.user = { profile: { roles: ['tenant_admin'] } };
    tenantAccessState.hasTenantRoleLevel = (requiredRole) => requiredRole === 'viewer';

    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={['/console/role-requests']}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/Welcome Page/)).toBeTruthy();
    });
    expect(screen.getByText(/reason=insufficient_role/)).toBeTruthy();
    expect(screen.getByText(/tenant=default/)).toBeTruthy();
    expect(screen.getByText(/next=%2Fconsole%2Frole-requests/)).toBeTruthy();
  });

  it('allows route access when active tenant role is tenant_admin', async () => {
    authState.user = { profile: { roles: ['tenant_admin'] } };
    tenantAccessState.hasTenantRoleLevel = (requiredRole) =>
      requiredRole === 'viewer' || requiredRole === 'publisher' || requiredRole === 'tenant_admin';

    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={['/console/role-requests']}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Role Requests Page')).toBeTruthy();
    });
  });
});
