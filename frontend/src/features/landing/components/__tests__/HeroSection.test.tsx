// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

const authState = {
  signinRedirect: vi.fn(),
};

vi.mock('react-oidc-context', () => ({
  useAuth: () => authState,
}));

import HeroSection from '../HeroSection';

describe('HeroSection', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('routes primary CTA to sign-in flow', () => {
    render(<HeroSection />);

    fireEvent.click(screen.getByTestId('landing-hero-primary-cta'));

    expect(authState.signinRedirect).toHaveBeenCalledTimes(1);
  });
});
