import { describe, expect, it } from 'vitest';
import { sanitizeLandingSummary } from '../useLandingSummary';

describe('sanitizeLandingSummary', () => {
  it('keeps only aggregate fields and normalizes malformed payloads', () => {
    const result = sanitizeLandingSummary(
      {
        tenant_slug: 'Default',
        published_dpps: '12',
        active_product_families: -10,
        dpps_with_traceability: 'NaN',
        latest_publish_at: 'invalid-date',
        generated_at: 'invalid-date',
        serialNumber: 'should-not-pass-through',
        payload: { leak: true },
      },
      'default',
    );

    expect(Object.keys(result).sort()).toEqual([
      'active_product_families',
      'dpps_with_traceability',
      'generated_at',
      'latest_publish_at',
      'published_dpps',
      'refresh_sla_seconds',
      'scope',
      'tenant_slug',
    ]);

    expect(result.tenant_slug).toBe('default');
    expect(result.published_dpps).toBe(12);
    expect(result.active_product_families).toBe(0);
    expect(result.dpps_with_traceability).toBe(0);
    expect(result.latest_publish_at).toBeNull();
    expect(result.generated_at).toBeNull();
    expect(result.scope).toBeNull();
    expect(result.refresh_sla_seconds).toBeNull();
  });
});
