// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const signinRedirect = vi.fn();

const authState = {
  isAuthenticated: false,
  isLoading: false,
  activeNavigator: null as string | null,
  signinRedirect,
};

vi.mock('react-oidc-context', () => ({
  useAuth: () => authState,
}));

import LoginPage from '../LoginPage';

function renderLogin(pathname: string) {
  return render(
    <MemoryRouter initialEntries={[pathname]}>
      <LoginPage />
    </MemoryRouter>,
  );
}

describe('LoginPage', () => {
  beforeEach(() => {
    signinRedirect.mockReset();
    authState.isAuthenticated = false;
    authState.isLoading = false;
    authState.activeNavigator = null;
  });

  it('starts Keycloak registration flow when mode=register', async () => {
    renderLogin('/login?mode=register');

    await waitFor(() => {
      expect(signinRedirect).toHaveBeenCalledWith({
        extraQueryParams: { kc_action: 'register' },
      });
    });
  });

  it('starts normal signin flow when mode is absent', async () => {
    renderLogin('/login');

    await waitFor(() => {
      expect(signinRedirect).toHaveBeenCalledWith();
    });
  });
});
