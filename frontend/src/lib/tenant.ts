import { useState } from 'react';

const STORAGE_KEY = 'dpp.tenantSlug';
const DEFAULT_TENANT = import.meta.env.VITE_DEFAULT_TENANT ?? 'default';

export function getTenantSlug(): string {
  if (typeof window === 'undefined') {
    return DEFAULT_TENANT;
  }
  return window.localStorage.getItem(STORAGE_KEY) || DEFAULT_TENANT;
}

export function setTenantSlug(slug: string): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, slug.trim().toLowerCase());
}

export function useTenantSlug(): [string, (slug: string) => void] {
  const [tenantSlug, setTenantSlugState] = useState<string>(getTenantSlug());
  const updateTenantSlug = (slug: string) => {
    const normalized = slug.trim().toLowerCase();
    setTenantSlugState(normalized);
    setTenantSlug(normalized);
  };

  return [tenantSlug, updateTenantSlug];
}
