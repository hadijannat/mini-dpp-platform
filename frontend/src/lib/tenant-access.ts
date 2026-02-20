import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { getApiErrorMessage, apiFetch } from '@/lib/api';
import { isAdmin } from '@/lib/auth';
import { getTenantSlug } from '@/lib/tenant';

type TenantRole = 'viewer' | 'publisher' | 'tenant_admin';
type RoleLevel = TenantRole | 'admin';

interface TenantMembership {
  slug: string;
  role: TenantRole;
}

const TENANT_ROLE_HIERARCHY: Record<TenantRole, TenantRole[]> = {
  viewer: ['viewer', 'publisher', 'tenant_admin'],
  publisher: ['publisher', 'tenant_admin'],
  tenant_admin: ['tenant_admin'],
};

async function fetchTenantMemberships(token: string): Promise<TenantMembership[]> {
  const response = await apiFetch('/api/v1/tenants/mine', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to load tenant memberships'));
  }
  const body = (await response.json()) as { tenants?: Array<{ slug?: string; role?: string }> };
  const memberships = Array.isArray(body.tenants) ? body.tenants : [];
  return memberships
    .map((membership) => {
      const slug = typeof membership.slug === 'string' ? membership.slug.trim().toLowerCase() : '';
      const role = membership.role;
      if (
        !slug ||
        (role !== 'viewer' && role !== 'publisher' && role !== 'tenant_admin')
      ) {
        return null;
      }
      return { slug, role };
    })
    .filter((membership): membership is TenantMembership => membership !== null);
}

export function useTenantAccess() {
  const auth = useAuth();
  const token = auth.user?.access_token ?? '';
  const selectedTenantSlug = getTenantSlug();
  const userIsAdmin = isAdmin(auth.user);

  const membershipsQuery = useQuery({
    queryKey: ['tenant-memberships', auth.user?.profile?.sub ?? 'anonymous'],
    queryFn: () => fetchTenantMemberships(token),
    enabled: auth.isAuthenticated && token.length > 0,
    staleTime: 60_000,
    retry: 1,
  });

  const activeMembership = useMemo(
    () =>
      membershipsQuery.data?.find((membership) => membership.slug === selectedTenantSlug) ?? null,
    [membershipsQuery.data, selectedTenantSlug],
  );

  const activeTenantRole: RoleLevel | null = userIsAdmin
    ? 'admin'
    : (activeMembership?.role ?? null);

  const hasTenantRoleLevel = (requiredRole: TenantRole | 'admin'): boolean => {
    if (requiredRole === 'admin') {
      return userIsAdmin;
    }
    if (userIsAdmin) {
      return true;
    }
    if (membershipsQuery.isLoading || membershipsQuery.isError) {
      return false;
    }
    if (!activeMembership) {
      return false;
    }
    return TENANT_ROLE_HIERARCHY[requiredRole].includes(activeMembership.role);
  };

  return {
    tenantSlug: selectedTenantSlug,
    activeTenantRole,
    hasTenantRoleLevel,
    isLoading: membershipsQuery.isLoading,
    isError: membershipsQuery.isError,
  };
}
