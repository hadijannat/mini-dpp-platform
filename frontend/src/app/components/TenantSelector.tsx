import { useEffect, useMemo, useState } from 'react';
import { useAuth } from 'react-oidc-context';
import { apiFetch, getApiErrorMessage } from '@/lib/api';
import { useTenantSlug } from '@/lib/tenant';
import { isAdmin as checkIsAdmin } from '@/lib/auth';

interface TenantOption {
  slug: string;
  name: string;
  status: string;
  role?: string;
}

export default function TenantSelector() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const userIsAdmin = checkIsAdmin(auth.user);
  const [tenantSlug, setTenantSlug] = useTenantSlug();
  const [tenants, setTenants] = useState<TenantOption[]>([]);
  const [error, setError] = useState<string | null>(null);

  const tenantOptions = useMemo(() => {
    if (tenants.length === 0) return [];
    if (tenants.some((tenant) => tenant.slug === tenantSlug)) {
      return tenants;
    }
    return [{ slug: tenantSlug, name: tenantSlug, status: 'unknown' }, ...tenants];
  }, [tenants, tenantSlug]);

  useEffect(() => {
    if (!token) return;
    const load = async () => {
      try {
        const response = await apiFetch('/api/v1/tenants/mine', {}, token);
        if (!response.ok) {
          throw new Error(await getApiErrorMessage(response, 'Failed to load tenants'));
        }
        const body = await response.json();
        if ((body.tenants || []).length > 0) {
          setTenants(body.tenants || []);
          return;
        }
        if (userIsAdmin) {
          const adminResponse = await apiFetch('/api/v1/tenants', {}, token);
          if (adminResponse.ok) {
            const adminBody = await adminResponse.json();
            setTenants(adminBody.tenants || []);
            return;
          }
        }
        setTenants(body.tenants || []);
      } catch (err) {
        setError((err as Error).message);
      }
    };
    load();
  }, [token, userIsAdmin]);

  const handleChange = (value: string) => {
    setTenantSlug(value);
    window.location.reload();
  };

  return (
    <div className="mt-4">
      <label className="text-[11px] uppercase tracking-wide text-gray-400">Tenant</label>
      {tenantOptions.length > 0 ? (
        <select
          value={tenantSlug}
          onChange={(event) => handleChange(event.target.value)}
          className="mt-1 w-full rounded-md bg-gray-800 text-gray-100 text-sm px-2 py-1 border border-gray-700"
        >
          {tenantOptions.map((tenant) => (
            <option key={tenant.slug} value={tenant.slug}>
              {tenant.name}
              {tenant.role ? ` (${tenant.role})` : ''}
            </option>
          ))}
        </select>
      ) : (
        <input
          value={tenantSlug}
          onChange={(event) => setTenantSlug(event.target.value)}
          onBlur={(event) => handleChange(event.target.value)}
          className="mt-1 w-full rounded-md bg-gray-800 text-gray-100 text-sm px-2 py-1 border border-gray-700"
          placeholder="tenant-slug"
        />
      )}
      {error && <p className="mt-1 text-xs text-red-400">{error}</p>}
    </div>
  );
}
