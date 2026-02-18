import { User } from 'oidc-client-ts';

/**
 * Extract all user roles from an OIDC token.
 *
 * Keycloak can configure roles in two locations:
 * - realm_access.roles: Realm-level roles
 * - resource_access[client_id].roles: Client-specific roles
 *
 * This function extracts roles from both locations and deduplicates them.
 */
export function getUserRoles(user: User | null | undefined): string[] {
  if (!user?.profile) {
    return [];
  }

  const profile = user.profile as Record<string, unknown>;
  const roles = new Set<string>();

  // Extract realm roles
  const realmAccess = profile.realm_access as { roles?: string[] } | undefined;
  if (realmAccess?.roles && Array.isArray(realmAccess.roles)) {
    realmAccess.roles.forEach((role) => roles.add(role));
  }

  // Extract client roles from resource_access
  const resourceAccess = profile.resource_access as Record<string, { roles?: string[] }> | undefined;
  if (resourceAccess && typeof resourceAccess === 'object') {
    // Check all clients, but prioritize the configured client ID
    const clientId = import.meta.env.VITE_KEYCLOAK_CLIENT_ID;

    // First, add roles from the configured client
    if (clientId && resourceAccess[clientId]?.roles) {
      resourceAccess[clientId].roles.forEach((role) => roles.add(role));
    }

    // Also check for roles in other common client names
    const clientNames = ['dpp-frontend', 'dpp-backend', 'account'];
    for (const name of clientNames) {
      if (name !== clientId && resourceAccess[name]?.roles) {
        resourceAccess[name].roles.forEach((role) => roles.add(role));
      }
    }
  }

  // Extract flat roles claim (some Keycloak configurations use this)
  const flatRoles = profile.roles as string[] | undefined;
  if (flatRoles && Array.isArray(flatRoles)) {
    flatRoles.forEach((role) => roles.add(role));
  }

  return Array.from(roles);
}

/**
 * Check if a user has a specific role.
 */
export function hasRole(user: User | null | undefined, role: string): boolean {
  return getUserRoles(user).includes(role);
}

/**
 * Check if a user has any of the specified roles.
 */
export function hasAnyRole(user: User | null | undefined, roles: string[]): boolean {
  const userRoles = getUserRoles(user);
  return roles.some((role) => userRoles.includes(role));
}

/**
 * Role hierarchy - higher roles include permissions of lower roles.
 */
const ROLE_HIERARCHY: Record<string, string[]> = {
  viewer: ['viewer', 'publisher', 'tenant_admin', 'admin'],
  publisher: ['publisher', 'tenant_admin', 'admin'],
  tenant_admin: ['tenant_admin', 'admin'],
  admin: ['admin'],
};

/**
 * Check if user has at least the specified role level (considering hierarchy).
 */
export function hasRoleLevel(user: User | null | undefined, requiredRole: string): boolean {
  const userRoles = getUserRoles(user);
  const allowedRoles = ROLE_HIERARCHY[requiredRole] || [requiredRole];
  return allowedRoles.some((role) => userRoles.includes(role));
}

/**
 * Check if user is an admin.
 */
export function isAdmin(user: User | null | undefined): boolean {
  return hasRole(user, 'admin');
}

/**
 * Check if user is a publisher (or higher).
 */
export function isPublisher(user: User | null | undefined): boolean {
  return hasRoleLevel(user, 'publisher');
}

/**
 * Check if user can review tenant role upgrade requests.
 */
export function canReviewRoleRequests(user: User | null | undefined): boolean {
  return hasAnyRole(user, ['tenant_admin', 'admin']);
}
