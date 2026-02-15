// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

vi.mock('./hooks/useLandingSummary', () => ({
  useLandingSummary: () => ({
    data: {
      tenant_slug: 'all',
      published_dpps: 15,
      active_product_families: 6,
      dpps_with_traceability: 4,
      latest_publish_at: '2026-02-13T17:56:41.383965+00:00',
      generated_at: '2026-02-15T12:01:03.563018+00:00',
      scope: 'all',
      refresh_sla_seconds: 30,
    },
    isLoading: false,
    isError: false,
  }),
  LANDING_SUMMARY_REFRESH_SLA_MS: 30_000,
}));

vi.mock('./hooks/useRegulatoryTimeline', () => ({
  useRegulatoryTimeline: () => ({
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
      ],
    },
    isLoading: false,
    isError: false,
  }),
}));

import LandingPage from './LandingPage';
import { landingContent } from './content/landingContent';

describe('LandingPage', () => {
  beforeEach(() => {
    cleanup();
  });

  it('renders redesigned five-section narrative in the intended order', () => {
    render(<LandingPage />);

    const main = screen.getByRole('main');
    const sectionIds = Array.from(main.querySelectorAll('section[id]')).map((section) => section.id);

    expect(sectionIds).toContain('proof-strip');
    expect(sectionIds).toContain('sample-passport');
    expect(sectionIds).toContain('evidence-governance');
    expect(sectionIds).toContain('launch');

    expect(sectionIds.indexOf('proof-strip')).toBeLessThan(sectionIds.indexOf('sample-passport'));
    expect(sectionIds.indexOf('sample-passport')).toBeLessThan(
      sectionIds.indexOf('evidence-governance'),
    );
    expect(sectionIds.indexOf('evidence-governance')).toBeLessThan(sectionIds.indexOf('launch'));

    const combinedText = main.textContent ?? '';
    const heroIndex = combinedText.indexOf(landingContent.hero.title);
    const proofIndex = combinedText.indexOf(landingContent.proofStrip.title);
    const sampleIndex = combinedText.indexOf(landingContent.samplePassport.title);
    const evidenceIndex = combinedText.indexOf(landingContent.evidenceRail.title);
    const launchIndex = combinedText.indexOf(landingContent.finalCta.title);

    expect(heroIndex).toBeGreaterThan(-1);
    expect(proofIndex).toBeGreaterThan(heroIndex);
    expect(sampleIndex).toBeGreaterThan(proofIndex);
    expect(evidenceIndex).toBeGreaterThan(sampleIndex);
    expect(launchIndex).toBeGreaterThan(evidenceIndex);
  });

  it('removes legacy sections from the main landing flow', () => {
    render(<LandingPage />);

    expect(screen.queryByText('How it works')).toBeNull();
    expect(screen.queryByText('LoopForge: CIRPASS Twin-Layer Lab')).toBeNull();
    expect(screen.queryByText('Common questions from compliance and engineering teams')).toBeNull();
  });
});
