// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

const mockNavigate = vi.fn();
const authState: {
  isAuthenticated: boolean;
  user: Record<string, unknown> | null;
  signinRedirect: ReturnType<typeof vi.fn>;
} = {
  isAuthenticated: true,
  user: { profile: { roles: ['viewer'] } },
  signinRedirect: vi.fn(),
};

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('react-oidc-context', () => ({
  useAuth: () => authState,
}));

import LandingHeader from '../LandingHeader';

describe('LandingHeader', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    authState.isAuthenticated = true;
    authState.user = { profile: { roles: ['viewer'] } };
  });

  it('routes authenticated viewers to welcome', () => {
    render(<LandingHeader />);

    const dashboardButtons = screen.getAllByRole('button', { name: 'Dashboard' });
    fireEvent.click(dashboardButtons[0]);

    expect(mockNavigate).toHaveBeenCalledWith('/welcome');
  });

  it('routes publisher users to console', () => {
    authState.user = { profile: { roles: ['publisher'] } };

    render(<LandingHeader />);

    const dashboardButtons = screen.getAllByRole('button', { name: 'Dashboard' });
    fireEvent.click(dashboardButtons[0]);

    expect(mockNavigate).toHaveBeenCalledWith('/console');
  });
});
