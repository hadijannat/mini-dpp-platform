import { useQuery } from '@tanstack/react-query';
import type { LandingSummary } from '@/api/types';
import { apiFetch, getApiErrorMessage } from '@/lib/api';

const DEFAULT_TENANT = (import.meta.env.VITE_DEFAULT_TENANT ?? 'default').trim().toLowerCase();

function toNonNegativeInt(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.max(0, Math.floor(value));
  }
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed)) {
      return Math.max(0, parsed);
    }
  }
  return 0;
}

function toIsoOrNull(value: unknown): string | null {
  if (typeof value !== 'string' || value.trim() === '') {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed.toISOString();
}

function toIso(value: unknown): string {
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toISOString();
    }
  }
  return new Date().toISOString();
}

export function sanitizeLandingSummary(payload: unknown, tenantSlug: string): LandingSummary {
  const source =
    payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {};

  return {
    tenant_slug:
      typeof source.tenant_slug === 'string' && source.tenant_slug.trim() !== ''
        ? source.tenant_slug.trim().toLowerCase()
        : tenantSlug,
    published_dpps: toNonNegativeInt(source.published_dpps),
    active_product_families: toNonNegativeInt(source.active_product_families),
    dpps_with_traceability: toNonNegativeInt(source.dpps_with_traceability),
    latest_publish_at: toIsoOrNull(source.latest_publish_at),
    generated_at: toIso(source.generated_at),
  };
}

async function fetchLandingSummary(tenantSlug: string): Promise<LandingSummary> {
  const response = await apiFetch(
    `/api/v1/public/${encodeURIComponent(tenantSlug)}/landing/summary`,
  );
  if (!response.ok) {
    throw new Error(
      await getApiErrorMessage(response, 'Unable to load aggregate landing summary.'),
    );
  }
  return sanitizeLandingSummary((await response.json()) as unknown, tenantSlug);
}

export function useLandingSummary(tenantSlug?: string) {
  const normalizedTenant = (tenantSlug ?? DEFAULT_TENANT).trim().toLowerCase() || DEFAULT_TENANT;

  return useQuery<LandingSummary>({
    queryKey: ['landing-summary', normalizedTenant],
    queryFn: () => fetchLandingSummary(normalizedTenant),
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    retry: 1,
  });
}
