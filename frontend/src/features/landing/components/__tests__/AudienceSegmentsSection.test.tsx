// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import AudienceSegmentsSection from '../AudienceSegmentsSection';

describe('AudienceSegmentsSection', () => {
  beforeEach(() => {
    cleanup();
    (globalThis as unknown as { IntersectionObserver: typeof IntersectionObserver }).IntersectionObserver =
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      } as unknown as typeof IntersectionObserver;
  });

  it('renders all four audience cards in the intended order', () => {
    render(<AudienceSegmentsSection />);

    const headings = screen
      .getAllByRole('heading', { level: 3 })
      .map((heading) => heading.textContent?.trim());

    expect(headings).toEqual([
      'Manufacturers',
      'Regulators & Auditors',
      'Recyclers & Repair Networks',
      'Consumers',
    ]);
  });
});
