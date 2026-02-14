// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

const mockUseRegulatoryTimeline = vi.fn();

vi.mock('../../hooks/useRegulatoryTimeline', () => ({
  useRegulatoryTimeline: (track?: string) => mockUseRegulatoryTimeline(track),
}));

import RegulatoryTimelineSection from '../RegulatoryTimelineSection';

describe('RegulatoryTimelineSection', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders loading placeholders', () => {
    mockUseRegulatoryTimeline.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    render(<RegulatoryTimelineSection />);

    expect(screen.getByTestId('regulatory-timeline-loading')).toBeTruthy();
    expect(screen.getByText('Verified DPP Timeline')).toBeTruthy();
  });

  it('renders verified event and opens detail dialog', () => {
    mockUseRegulatoryTimeline.mockReturnValue({
      data: {
        generated_at: '2026-02-10T12:00:00Z',
        fetched_at: '2026-02-10T12:00:00Z',
        source_status: 'fresh',
        refresh_sla_seconds: 82800,
        digest_sha256: 'abc',
        events: [
          {
            id: 'espr-entry-into-force',
            date: '2024-07-18',
            date_precision: 'day',
            track: 'regulation',
            title: 'ESPR entered into force',
            plain_summary: 'Regulation baseline.',
            audience_tags: ['brands'],
            status: 'past',
            verified: true,
            verification: {
              checked_at: '2026-02-10T12:00:00Z',
              method: 'content-match',
              confidence: 'high',
            },
            sources: [
              {
                label: 'European Commission — ESPR',
                url: 'https://commission.europa.eu',
                publisher: 'European Commission',
                retrieved_at: '2026-02-10T12:00:00Z',
                sha256: 'a'.repeat(64),
              },
            ],
          },
          {
            id: 'battery-passport',
            date: '2027-02-18',
            date_precision: 'day',
            track: 'regulation',
            title: 'Battery passport requirement begins',
            plain_summary: 'Upcoming milestone.',
            audience_tags: ['battery-manufacturers'],
            status: 'upcoming',
            verified: false,
            verification: {
              checked_at: '2026-02-10T12:00:00Z',
              method: 'source-hash',
              confidence: 'medium',
            },
            sources: [],
          },
        ],
      },
      isLoading: false,
      isError: false,
    });

    render(<RegulatoryTimelineSection />);

    expect(screen.getByText('Verified DPP Timeline')).toBeTruthy();
    expect(screen.getAllByText('ESPR entered into force').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Verified').length).toBeGreaterThan(0);
    expect(screen.getByTestId('timeline-next-milestone')).toBeTruthy();

    fireEvent.click(screen.getByTestId('timeline-card-espr-entry-into-force'));
    expect(screen.getByText('Official citations')).toBeTruthy();
    expect(screen.getByRole('link', { name: /European Commission — ESPR/i })).toBeTruthy();
  });

  it('shows fallback text when API fails', () => {
    mockUseRegulatoryTimeline.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    render(<RegulatoryTimelineSection />);

    expect(screen.getByText(/showing fallback milestones/i)).toBeTruthy();
    expect(screen.getAllByText('ESPR entered into force').length).toBeGreaterThan(0);
  });
});
