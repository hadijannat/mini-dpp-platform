import { useQuery } from '@tanstack/react-query';
import type { LandingSummary } from '@/api/types';
import { apiFetch, getApiErrorMessage } from '@/lib/api';

export const LANDING_SUMMARY_REFRESH_SLA_MS = 30_000;
const DEFAULT_TENANT = (import.meta.env.VITE_DEFAULT_TENANT ?? 'default').trim().toLowerCase();
const LANDING_SUMMARY_GC_MS = 30 * 60 * 1000;

export type LandingSummaryScope = 'all' | 'default';

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

function toOptionalScope(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  return normalized.length > 0 ? normalized : null;
}

function toNullableNonNegativeInt(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value >= 0 ? Math.floor(value) : null;
  }
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed) && parsed >= 0) {
      return parsed;
    }
  }
  return null;
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
    generated_at: toIsoOrNull(source.generated_at),
    scope: toOptionalScope(source.scope),
    refresh_sla_seconds: toNullableNonNegativeInt(source.refresh_sla_seconds),
  };
}

async function fetchLandingSummary(
  tenantSlug: string | null,
  scope: LandingSummaryScope,
): Promise<LandingSummary> {
  const path = tenantSlug
    ? `/api/v1/public/${encodeURIComponent(tenantSlug)}/landing/summary`
    : `/api/v1/public/landing/summary?scope=${encodeURIComponent(scope)}`;

  const response = await apiFetch(path);
  if (!response.ok) {
    throw new Error(
      await getApiErrorMessage(response, 'Unable to load aggregate landing summary.'),
    );
  }

  const fallbackTenant = tenantSlug ?? (scope === 'all' ? 'all' : DEFAULT_TENANT);
  return sanitizeLandingSummary((await response.json()) as unknown, fallbackTenant);
}

export function useLandingSummary(
  tenantSlug?: string,
  scope: LandingSummaryScope = 'all',
  enabled = true,
) {
  const normalizedTenant = tenantSlug?.trim().toLowerCase() ?? '';
  const useTenantScopedSummary = normalizedTenant.length > 0;
  const normalizedScope = scope === 'default' ? 'default' : 'all';

  return useQuery<LandingSummary>({
    queryKey: ['landing-summary', useTenantScopedSummary ? normalizedTenant : normalizedScope],
    queryFn: () =>
      fetchLandingSummary(
        useTenantScopedSummary ? normalizedTenant : null,
        normalizedScope,
      ),
    enabled,
    staleTime: 0,
    gcTime: LANDING_SUMMARY_GC_MS,
    retry: 1,
    refetchInterval: enabled ? LANDING_SUMMARY_REFRESH_SLA_MS : false,
    refetchIntervalInBackground: enabled,
  });
}
