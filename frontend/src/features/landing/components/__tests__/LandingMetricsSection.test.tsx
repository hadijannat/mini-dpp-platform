// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

const mockUseLandingSummary = vi.fn();

vi.mock('../../hooks/useLandingSummary', () => ({
  useLandingSummary: (tenantSlug?: string) => mockUseLandingSummary(tenantSlug),
}));

import LandingMetricsSection from '../LandingMetricsSection';

describe('LandingMetricsSection', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders loading state placeholders', () => {
    mockUseLandingSummary.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    render(<LandingMetricsSection tenantSlug="default" />);

    expect(screen.getByTestId('landing-metrics-loading')).toBeTruthy();
    expect(screen.getAllByTestId('landing-metrics-loading-card')).toHaveLength(4);
  });

  it('renders aggregate values on success and ignores unexpected sensitive fields', () => {
    mockUseLandingSummary.mockReturnValue({
      data: {
        tenant_slug: 'default',
        published_dpps: 12,
        active_product_families: 4,
        dpps_with_traceability: 7,
        latest_publish_at: '2026-02-09T12:00:00Z',
        generated_at: '2026-02-10T00:00:00Z',
        serialNumber: 'SN-DO-NOT-SHOW',
        payload: { unexpected: true },
      },
      isLoading: false,
      isError: false,
    });

    render(<LandingMetricsSection tenantSlug="default" />);

    expect(screen.getByTestId('landing-metrics-success')).toBeTruthy();
    expect(screen.getByTestId('landing-metric-published-dpps')).toBeTruthy();
    expect(screen.getByText('12')).toBeTruthy();
    expect(screen.queryByText('SN-DO-NOT-SHOW')).toBeNull();
    expect(screen.queryByText('serialNumber')).toBeNull();
    expect(screen.queryByText('payload')).toBeNull();
  });

  it('renders fallback content when summary endpoint fails', () => {
    mockUseLandingSummary.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    render(<LandingMetricsSection tenantSlug="default" />);

    expect(screen.getByTestId('landing-metrics-fallback')).toBeTruthy();
    expect(screen.getByText('Live metrics temporarily unavailable')).toBeTruthy();
  });
});
