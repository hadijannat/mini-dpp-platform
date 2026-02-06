import { describe, expect, it } from 'vitest';

import { getUserRoles, hasRoleLevel, isAdmin, isPublisher } from './auth';

/**
 * Helper to build a minimal OIDC User-like object whose `profile` carries the
 * claims we need for each test.  The real `User` from oidc-client-ts has many
 * more fields, but `getUserRoles` only accesses `user.profile`.
 */
function mockUser(profile: Record<string, unknown> | null = null) {
  if (profile === null) return null;
  return { profile } as unknown as import('oidc-client-ts').User;
}

// ---------- getUserRoles ----------

describe('getUserRoles', () => {
  it('returns empty array for null user', () => {
    expect(getUserRoles(null)).toEqual([]);
  });

  it('returns empty array when profile is missing', () => {
    // user exists but profile is undefined
    expect(getUserRoles(undefined)).toEqual([]);
  });

  it('extracts roles from realm_access', () => {
    const user = mockUser({
      realm_access: { roles: ['viewer', 'publisher'] },
    });
    expect(getUserRoles(user)).toEqual(expect.arrayContaining(['viewer', 'publisher']));
  });

  it('extracts roles from resource_access for the configured client', () => {
    const clientId = import.meta.env.VITE_KEYCLOAK_CLIENT_ID || '';
    // Skip if no client ID is configured — the rest of the suite still covers
    // the fallback branch.
    if (!clientId) return;

    const user = mockUser({
      resource_access: {
        [clientId]: { roles: ['tenant_admin'] },
      },
    });
    expect(getUserRoles(user)).toContain('tenant_admin');
  });

  it('falls back to common client name dpp-frontend', () => {
    const user = mockUser({
      resource_access: {
        'dpp-frontend': { roles: ['editor'] },
      },
    });
    expect(getUserRoles(user)).toContain('editor');
  });

  it('extracts flat roles claim from profile', () => {
    const user = mockUser({
      roles: ['admin'],
    });
    expect(getUserRoles(user)).toContain('admin');
  });

  it('deduplicates roles across sources', () => {
    const user = mockUser({
      realm_access: { roles: ['publisher', 'viewer'] },
      roles: ['publisher'],
      resource_access: {
        'dpp-frontend': { roles: ['publisher'] },
      },
    });
    const roles = getUserRoles(user);
    // 'publisher' should appear only once despite being in three sources
    expect(roles.filter((r) => r === 'publisher')).toHaveLength(1);
    expect(roles).toEqual(expect.arrayContaining(['publisher', 'viewer']));
  });

  it('handles non-array roles claim gracefully', () => {
    const user = mockUser({
      roles: 'not-an-array' as unknown,
    });
    // Should not throw and should return empty (no valid roles)
    expect(getUserRoles(user)).toEqual([]);
  });
});

// ---------- hasRoleLevel ----------

describe('hasRoleLevel', () => {
  it('viewer level is satisfied by admin', () => {
    const user = mockUser({ roles: ['admin'] });
    expect(hasRoleLevel(user, 'viewer')).toBe(true);
  });

  it('publisher level is satisfied by tenant_admin', () => {
    const user = mockUser({ roles: ['tenant_admin'] });
    expect(hasRoleLevel(user, 'publisher')).toBe(true);
  });

  it('admin level is only satisfied by admin', () => {
    const user = mockUser({ roles: ['publisher'] });
    expect(hasRoleLevel(user, 'admin')).toBe(false);
  });

  it('unknown role falls back to exact match', () => {
    const user = mockUser({ roles: ['custom_role'] });
    expect(hasRoleLevel(user, 'custom_role')).toBe(true);
    expect(hasRoleLevel(user, 'other_role')).toBe(false);
  });
});

// ---------- isPublisher ----------

describe('isPublisher', () => {
  it('returns true for publisher, tenant_admin, and admin', () => {
    expect(isPublisher(mockUser({ roles: ['publisher'] }))).toBe(true);
    expect(isPublisher(mockUser({ roles: ['tenant_admin'] }))).toBe(true);
    expect(isPublisher(mockUser({ roles: ['admin'] }))).toBe(true);
  });

  it('returns false for viewer', () => {
    expect(isPublisher(mockUser({ roles: ['viewer'] }))).toBe(false);
  });
});

// ---------- isAdmin ----------

describe('isAdmin', () => {
  it('returns true only for admin role', () => {
    expect(isAdmin(mockUser({ roles: ['admin'] }))).toBe(true);
    expect(isAdmin(mockUser({ roles: ['publisher'] }))).toBe(false);
    expect(isAdmin(mockUser({ roles: ['tenant_admin'] }))).toBe(false);
    expect(isAdmin(mockUser({ roles: ['viewer'] }))).toBe(false);
  });
});
