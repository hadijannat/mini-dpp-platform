import { describe, expect, it } from 'vitest';
import { sanitizeRegulatoryTimeline } from '../useRegulatoryTimeline';

describe('sanitizeRegulatoryTimeline', () => {
  it('normalizes malformed payload and drops unknown fields', () => {
    const result = sanitizeRegulatoryTimeline({
      generated_at: 'invalid-date',
      fetched_at: '2026-02-10T12:00:00Z',
      source_status: 'unknown',
      refresh_sla_seconds: '-1',
      digest_sha256: '',
      events: [
        {
          id: 'espr-entry-into-force',
          date: '2024-07-18',
          date_precision: 'day',
          track: 'regulation',
          title: 'ESPR entered into force',
          plain_summary: 'Summary',
          audience_tags: ['brands', 1, ''],
          status: 'past',
          verified: true,
          verification: {
            checked_at: 'invalid',
            method: 'content-match',
            confidence: 'high',
            raw: 'blocked',
          },
          sources: [
            {
              label: 'Commission',
              url: 'https://commission.europa.eu',
              publisher: 'European Commission',
              retrieved_at: 'invalid',
              sha256: 'abc',
            },
            {
              label: '',
              url: 'https://example.com',
              publisher: 'Example',
              retrieved_at: '2026-02-10T12:00:00Z',
            },
          ],
          serialNumber: 'blocked',
        },
      ],
      payload: { leak: true },
    });

    expect(Object.keys(result).sort()).toEqual([
      'digest_sha256',
      'events',
      'fetched_at',
      'generated_at',
      'refresh_sla_seconds',
      'source_status',
    ]);

    expect(result.source_status).toBe('fresh');
    expect(result.refresh_sla_seconds).toBe(82800);
    expect(result.events).toHaveLength(1);
    expect(result.events[0].audience_tags).toEqual(['brands']);
    expect(result.events[0].sources).toHaveLength(1);
    expect(result.events[0].sources[0].sha256).toBe('abc');
    expect(result.events[0].verification.method).toBe('content-match');
    expect(result.events[0].verification.confidence).toBe('high');
  });
});
