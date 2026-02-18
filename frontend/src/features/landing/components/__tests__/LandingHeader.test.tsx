// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import LandingHeader from '../LandingHeader';

let desktopBreakpointMatch = false;
let matchMediaListeners: Array<(event: MediaQueryListEvent) => void> = [];

function emitDesktopBreakpointChange(matches: boolean) {
  desktopBreakpointMatch = matches;
  const event = { matches } as MediaQueryListEvent;
  matchMediaListeners.forEach((listener) => listener(event));
}

describe('LandingHeader', () => {
  beforeEach(() => {
    cleanup();
    desktopBreakpointMatch = false;
    matchMediaListeners = [];
    (globalThis as unknown as { IntersectionObserver: typeof IntersectionObserver }).IntersectionObserver =
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      } as unknown as typeof IntersectionObserver;
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: (query: string) => ({
        matches: query === '(min-width: 1280px)' ? desktopBreakpointMatch : false,
        media: query,
        onchange: null,
        addEventListener: (_type: 'change', listener: (event: MediaQueryListEvent) => void) => {
          matchMediaListeners.push(listener);
        },
        removeEventListener: (_type: 'change', listener: (event: MediaQueryListEvent) => void) => {
          matchMediaListeners = matchMediaListeners.filter((current) => current !== listener);
        },
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => true,
      }),
    });
  });

  it('renders desktop CTAs and docs navigation', () => {
    render(<LandingHeader />);

    expect(screen.getAllByRole('link', { name: 'Open demo' })[0].getAttribute('href')).toBe(
      '#sample-passport',
    );
    expect(screen.getAllByRole('link', { name: 'Create account' })[0].getAttribute('href')).toBe(
      '/login?mode=register',
    );
    expect(screen.getAllByRole('link', { name: 'Sign in' })[0].getAttribute('href')).toBe('/login');
    expect(screen.getByRole('link', { name: 'Docs' }).getAttribute('href')).toBe(
      'https://github.com/hadijannat/mini-dpp-platform/tree/main/docs/public',
    );
  });

  it('mobile menu reveals FAQ and auth actions', () => {
    render(<LandingHeader />);

    fireEvent.click(screen.getByRole('button', { name: /open menu/i }));

    expect(screen.getAllByRole('link', { name: 'FAQ' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: 'Open demo' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: 'Create account' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: 'Sign in' }).length).toBeGreaterThan(0);
  });

  it('closes mobile menu when switching to desktop breakpoint', async () => {
    const { container } = render(<LandingHeader />);

    fireEvent.click(screen.getByRole('button', { name: /open menu/i }));
    expect(container.querySelector('header')?.getAttribute('data-mobile-open')).toBe('true');

    emitDesktopBreakpointChange(true);

    await waitFor(() => {
      expect(container.querySelector('header')?.getAttribute('data-mobile-open')).toBe('false');
    });
  });
});
