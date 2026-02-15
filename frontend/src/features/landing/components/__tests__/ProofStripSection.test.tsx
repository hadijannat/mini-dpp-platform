// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('../LandingMetricsSection', () => ({
  default: (props: { scope?: string; variant?: string }) => (
    <div
      data-testid="mock-landing-metrics"
      data-scope={props.scope ?? ''}
      data-variant={props.variant ?? ''}
    />
  ),
}));

import ProofStripSection from '../ProofStripSection';

describe('ProofStripSection', () => {
  it('renders compact proof content and embeds compact metrics', () => {
    render(<ProofStripSection />);

    expect(screen.getByRole('heading', { level: 2 }).textContent).toContain(
      'Evidence first, marketing second',
    );
    expect(screen.getByTestId('proof-strip-badges')).toBeTruthy();
    expect(screen.getByText('Aggregate-only metrics')).toBeTruthy();
    expect(screen.getByText('Route-level evidence')).toBeTruthy();
    expect(screen.getByText('No record-level identifiers')).toBeTruthy();

    const metrics = screen.getByTestId('mock-landing-metrics');
    expect(metrics.getAttribute('data-scope')).toBe('all');
    expect(metrics.getAttribute('data-variant')).toBe('compact');

    expect(screen.getByTestId('proof-strip-privacy-link').getAttribute('href')).toContain(
      'public-data-exposure-policy.md',
    );
  });
});
