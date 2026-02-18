// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const authState = {
  isAuthenticated: true,
  isLoading: false,
  user: { profile: { roles: ['tenant_admin'] } },
};

vi.mock('react-oidc-context', () => ({
  useAuth: () => authState,
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
  default: () => <div>Welcome Page</div>,
}));

import App from './App';

describe('App role requests route', () => {
  it('allows tenant_admin to access /console/role-requests', async () => {
    authState.user = { profile: { roles: ['tenant_admin'] } };

    render(
      <MemoryRouter initialEntries={['/console/role-requests']}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Role Requests Page')).toBeTruthy();
    });
  });
});
