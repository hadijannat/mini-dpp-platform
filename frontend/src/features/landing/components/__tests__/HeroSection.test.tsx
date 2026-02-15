// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import HeroSection from '../HeroSection';

describe('HeroSection', () => {
  const originalLocation = window.location;

  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.restoreAllMocks();

    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        ...originalLocation,
        assign: vi.fn(),
      },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });

  it('scrolls to sample section from primary CTA', () => {
    const scrollIntoView = vi.fn();
    const originalGetElementById = document.getElementById.bind(document);
    vi.spyOn(document, 'getElementById').mockImplementation((id: string) => {
      if (id === 'sample-passport') {
        return { scrollIntoView } as unknown as HTMLElement;
      }
      return originalGetElementById(id);
    });

    render(<HeroSection />);

    fireEvent.click(screen.getByTestId('landing-hero-primary-cta'));

    expect(scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it('navigates to CIRPASS lab from secondary CTA', () => {
    render(<HeroSection />);

    fireEvent.click(screen.getByTestId('landing-hero-secondary-cta'));

    expect(window.location.assign).toHaveBeenCalledWith('/cirpass-lab');
  });

  it('renders required proof pills', () => {
    render(<HeroSection />);

    expect(screen.getByText('Regulation (EU) 2024/1781 aligned posture')).toBeTruthy();
    expect(screen.getByText('AAS + DPP4.0 implementation evidence')).toBeTruthy();
    expect(screen.getByText('Aggregate-only public landing contract')).toBeTruthy();
  });

  it('renders the new conversion-first headline', () => {
    render(<HeroSection />);

    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Ship passport experiences fast');
  });

  it('renders the compact AAS shell model in hero preview', () => {
    render(<HeroSection />);

    expect(screen.getByRole('heading', { level: 2 }).textContent).toContain(
      'Asset Administration Shell (IEC 63278)',
    );
  });
});
