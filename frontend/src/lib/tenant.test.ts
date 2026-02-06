// @vitest-environment jsdom
import { describe, expect, it, beforeEach } from 'vitest';

import { getTenantSlug, setTenantSlug } from './tenant';

const STORAGE_KEY = 'dpp.tenantSlug';

describe('getTenantSlug', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('returns the default tenant when localStorage is empty', () => {
    const result = getTenantSlug();
    // Should be DEFAULT_TENANT which is import.meta.env.VITE_DEFAULT_TENANT ?? 'default'
    const expected = import.meta.env.VITE_DEFAULT_TENANT ?? 'default';
    expect(result).toBe(expected);
  });

  it('returns the stored value from localStorage', () => {
    window.localStorage.setItem(STORAGE_KEY, 'acme-corp');
    expect(getTenantSlug()).toBe('acme-corp');
  });
});

describe('setTenantSlug', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('normalizes whitespace by trimming', () => {
    setTenantSlug('  my-tenant  ');
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('my-tenant');
  });

  it('normalizes case to lowercase', () => {
    setTenantSlug('My-Tenant');
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('my-tenant');
  });

  it('round-trips correctly with getTenantSlug', () => {
    setTenantSlug('  RoundTrip-Tenant  ');
    expect(getTenantSlug()).toBe('roundtrip-tenant');
  });

  it('normalizes both whitespace and case together', () => {
    setTenantSlug('  UPPER  ');
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('upper');
  });
});
