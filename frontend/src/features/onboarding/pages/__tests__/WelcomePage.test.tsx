// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const mockNavigate = vi.fn();
const signoutRedirect = vi.fn();
const authState = {
  user: { access_token: 'token-123', profile: {} },
  isAuthenticated: true,
  isLoading: false,
  signinRedirect: vi.fn(),
  signoutRedirect,
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

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
  getApiErrorMessage: vi.fn().mockResolvedValue('API error'),
}));

vi.mock('../../components/RoleRequestCard', () => ({
  default: ({ tenantSlug }: { tenantSlug: string }) => <div>Role request card for {tenantSlug}</div>,
}));

import { apiFetch } from '@/lib/api';
import WelcomePage from '../WelcomePage';

function renderWelcome(initialEntry: string = '/welcome') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <WelcomePage />
    </MemoryRouter>,
  );
}

describe('WelcomePage', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    authState.user = { access_token: 'token-123', profile: {} };
    authState.isAuthenticated = true;
  });

  it('renders email verification blocker and can resend verification', async () => {
    (apiFetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            provisioned: false,
            tenant_slug: 'default',
            role: null,
            email_verified: false,
            blockers: ['email_unverified'],
            next_actions: ['resend_verification', 'go_home'],
          }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ queued: true }),
      });

    renderWelcome('/welcome?reason=insufficient_role');

    expect(await screen.findByText('Email verification required')).toBeTruthy();
    expect(
      screen.getByText('Your current role cannot access the publisher console. You can continue here.'),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Resend verification email' }));

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        '/api/v1/onboarding/resend-verification',
        expect.objectContaining({ method: 'POST' }),
        'token-123',
      );
    });

    expect(
      await screen.findByText('Verification email sent. Please check your inbox and spam folder.'),
    ).toBeTruthy();
  });

  it('renders viewer actions with role request card and supports go-home/signout', async () => {
    (apiFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          provisioned: true,
          tenant_slug: 'default',
          role: 'viewer',
          email_verified: true,
          blockers: [],
          next_actions: ['request_role_upgrade', 'go_home'],
        }),
    });

    renderWelcome();

    expect(await screen.findByText('Role request card for default')).toBeTruthy();

    const goHomeButton = screen.getAllByRole('button', { name: 'Go Home' })[0];
    fireEvent.click(goHomeButton);
    expect(mockNavigate).toHaveBeenCalledWith('/');

    fireEvent.click(screen.getByRole('button', { name: 'Sign Out' }));
    expect(signoutRedirect).toHaveBeenCalledTimes(1);
  });

  it('redirects to console for publisher+ users', async () => {
    (apiFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          provisioned: true,
          tenant_slug: 'default',
          role: 'publisher',
          email_verified: true,
          blockers: [],
          next_actions: ['go_home'],
        }),
    });

    renderWelcome();

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/console', { replace: true });
    });
  });
});
