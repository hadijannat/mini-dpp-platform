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
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={[initialEntry]}>
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
        json: () =>
          Promise.resolve({
            queued: true,
            cooldown_seconds: 30,
            next_allowed_at: '2026-02-18T12:00:30Z',
          }),
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
      await screen.findByText(/Verification email sent\. Please check your inbox and spam folder\./),
    ).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Resend available in 30s' })).toBeTruthy();
  });

  it('handles resend cooldown responses with retry guidance', async () => {
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
        ok: false,
        headers: {
          get: (name: string) => {
            if (name === 'content-type') return 'application/json';
            if (name === 'Retry-After') return '12';
            return null;
          },
        },
        json: () =>
          Promise.resolve({
            detail: {
              code: 'verification_resend_cooldown',
              message: 'Please wait before retrying.',
              cooldown_seconds: 12,
              next_allowed_at: '2026-02-18T12:00:12Z',
            },
          }),
      });

    renderWelcome();

    fireEvent.click(await screen.findByRole('button', { name: 'Resend verification email' }));

    expect(
      await screen.findByText('Please wait 12 seconds before requesting another verification email.'),
    ).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Resend available in 12s' })).toBeTruthy();
  });

  it('uses tenant query context for insufficient-role guidance and role requests', async () => {
    (apiFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          provisioned: true,
          tenant_slug: 'default',
          role: 'viewer',
          email_verified: true,
          blockers: [],
          next_actions: ['go_home'],
        }),
    });

    renderWelcome('/welcome?reason=insufficient_role&tenant=acme');

    expect(
      await screen.findByText(
        'Your current role cannot access the publisher console for tenant "acme". You can continue here.',
      ),
    ).toBeTruthy();
    expect(screen.getByText('Role request card for acme')).toBeTruthy();
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

  it('shows verify-email guidance when provision returns onboarding_email_not_verified', async () => {
    (apiFetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            provisioned: false,
            tenant_slug: 'default',
            role: null,
            email_verified: true,
            blockers: [],
            next_actions: ['provision', 'go_home'],
          }),
      })
      .mockResolvedValueOnce({
        ok: false,
        headers: {
          get: (name: string) => (name === 'content-type' ? 'application/json' : null),
        },
        json: () =>
          Promise.resolve({
            detail: {
              code: 'onboarding_email_not_verified',
              message: 'Email verification required',
            },
          }),
      })
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
      });

    renderWelcome();

    const getStarted = await screen.findByRole('button', { name: 'Get Started' });
    fireEvent.click(getStarted);

    expect(
      await screen.findByText(
        'Please verify your email first, then refresh access or resend verification.',
      ),
    ).toBeTruthy();

    await waitFor(() => {
      expect(apiFetch).toHaveBeenNthCalledWith(3, '/api/v1/onboarding/status', {}, 'token-123');
    });
  });
});
