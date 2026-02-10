// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const authState: {
  isAuthenticated: boolean;
  user: Record<string, unknown> | null;
} = {
  isAuthenticated: true,
  user: { profile: { roles: ['viewer'] } },
};

vi.mock('react-oidc-context', () => ({
  useAuth: () => authState,
}));

import ProtectedRoute from '../ProtectedRoute';

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
        <Route path="/welcome" element={<div>Welcome Page</div>} />
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
  });

  it('redirects authenticated viewers to welcome for publisher-only routes', async () => {
    renderRoutes('/console');

    expect(await screen.findByText('Welcome Page')).toBeTruthy();
    expect(screen.queryByText('Console')).toBeNull();
  });

  it('redirects unauthenticated users to landing and stores intended route', async () => {
    authState.isAuthenticated = false;
    authState.user = null;

    renderRoutes('/console');

    expect(await screen.findByText('Landing')).toBeTruthy();
    expect(sessionStorage.getItem('auth.redirectUrl')).toBe('/console');
  });

  it('renders access denied if user does not have viewer-level access', async () => {
    authState.isAuthenticated = true;
    authState.user = { profile: { roles: [] } };

    renderRoutes('/console');

    expect(await screen.findByText('Access Denied')).toBeTruthy();
    expect(screen.queryByText('Welcome Page')).toBeNull();
  });
});
