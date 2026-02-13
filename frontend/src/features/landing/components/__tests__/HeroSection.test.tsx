// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import HeroSection from '../HeroSection';

describe('HeroSection', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.restoreAllMocks();
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

  it('renders required proof pills', () => {
    render(<HeroSection />);

    expect(screen.getByText('Regulation (EU) 2024/1781 aligned posture')).toBeTruthy();
    expect(screen.getByText('DPP4.0 Template Ingestion')).toBeTruthy();
    expect(screen.getByText('AAS + Dataspace-ready APIs')).toBeTruthy();
  });

  it('renders the new conversion-first headline', () => {
    render(<HeroSection />);

    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain(
      'Digital Product Passport Platform for ESPR-ready product data',
    );
  });
});
