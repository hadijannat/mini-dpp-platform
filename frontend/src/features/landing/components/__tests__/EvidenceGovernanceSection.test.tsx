// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

const mockUseRegulatoryTimeline = vi.fn();

vi.mock('../../hooks/useRegulatoryTimeline', () => ({
  useRegulatoryTimeline: () => mockUseRegulatoryTimeline(),
}));

import EvidenceGovernanceSection from '../EvidenceGovernanceSection';

describe('EvidenceGovernanceSection', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders live timeline highlights and standards evidence cards', () => {
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
            sources: [],
          },
          {
            id: 'registry-deadline',
            date: '2026-07-19',
            date_precision: 'day',
            track: 'regulation',
            title: 'DPP registry deadline',
            plain_summary: 'Registry milestone.',
            audience_tags: ['authorities'],
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

    render(<EvidenceGovernanceSection />);

    expect(screen.getByRole('heading', { level: 2 }).textContent).toContain(
      'Regulatory timing, standards mapping, and public boundary in one place',
    );
    expect(screen.getByText('ESPR entered into force')).toBeTruthy();
    expect(screen.getByText('DPP registry deadline')).toBeTruthy();
    expect(screen.getByTestId('evidence-standards-cards')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Public router evidence/i })).toBeTruthy();
  });

  it('uses fallback milestones when timeline query fails', () => {
    mockUseRegulatoryTimeline.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    render(<EvidenceGovernanceSection />);

    expect(screen.getByTestId('evidence-timeline-fallback')).toBeTruthy();
    expect(screen.getByText('ESPR entered into force')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Public data exposure policy/i })).toBeTruthy();
  });
});
