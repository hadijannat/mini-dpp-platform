// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import LandingHeader from '../LandingHeader';

describe('LandingHeader', () => {
  beforeEach(() => {
    cleanup();
    (globalThis as unknown as { IntersectionObserver: typeof IntersectionObserver }).IntersectionObserver =
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      } as unknown as typeof IntersectionObserver;
  });

  it('renders desktop CTAs and docs navigation', () => {
    render(<LandingHeader />);

    expect(screen.getAllByRole('link', { name: 'Open sample' })[0].getAttribute('href')).toBe(
      '#sample-passport',
    );
    expect(screen.getAllByRole('link', { name: 'Sign in' })[0].getAttribute('href')).toBe('/login');
    expect(screen.getByRole('link', { name: 'Docs' }).getAttribute('href')).toBe(
      'https://github.com/hadijannat/mini-dpp-platform/tree/main/docs/public',
    );
    expect(screen.getByRole('link', { name: 'Evidence' }).getAttribute('href')).toBe(
      '#evidence-governance',
    );
  });

  it('mobile menu reveals conversion and auth actions', () => {
    render(<LandingHeader />);

    fireEvent.click(screen.getByRole('button', { name: /open menu/i }));

    expect(screen.getAllByRole('link', { name: 'Launch' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: 'Open sample' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: 'Sign in' }).length).toBeGreaterThan(0);
  });
});
