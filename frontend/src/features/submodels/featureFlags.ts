const DEFAULT_CANARY_TENANTS = '';
const DEFAULT_SURFACES = 'publisher,editor,viewer';

export type SubmodelSurface = 'publisher' | 'editor' | 'viewer';

export type SubmodelSurfaceFlags = Record<SubmodelSurface, boolean>;

export type SubmodelUxRollout = {
  tenant: string;
  enabled: boolean;
  isCanaryTenant: boolean;
  source: 'global' | 'canary' | 'override';
  surfaces: SubmodelSurfaceFlags;
};

function normalizeTenant(input: string | null | undefined): string {
  return String(input ?? '')
    .trim()
    .toLowerCase();
}

function parseCsv(input: string | undefined, fallback = ''): Set<string> {
  const raw = (input ?? fallback).trim();
  if (!raw) return new Set();
  return new Set(
    raw
      .split(',')
      .map((part) => normalizeTenant(part))
      .filter(Boolean),
  );
}

function parseBoolean(value: string | undefined, fallback: boolean): boolean {
  if (value == null) return fallback;
  const normalized = value.trim().toLowerCase();
  if (['1', 'true', 'yes', 'on'].includes(normalized)) return true;
  if (['0', 'false', 'no', 'off'].includes(normalized)) return false;
  return fallback;
}

function parseSurfaceCsv(input: string | undefined): Set<SubmodelSurface> {
  const defaults = parseCsv(DEFAULT_SURFACES, DEFAULT_SURFACES);
  const source = parseCsv(input, DEFAULT_SURFACES);
  const output: Set<SubmodelSurface> = new Set();
  for (const entry of source.size > 0 ? source : defaults) {
    if (entry === 'publisher' || entry === 'editor' || entry === 'viewer') {
      output.add(entry);
    }
  }
  return output;
}

function parseTenantOverrides(
  input: string | undefined,
): Record<string, Set<SubmodelSurface>> {
  if (!input) return {};
  try {
    const parsed = JSON.parse(input) as Record<string, unknown>;
    const result: Record<string, Set<SubmodelSurface>> = {};
    for (const [tenant, surfaceValue] of Object.entries(parsed)) {
      const normalizedTenant = normalizeTenant(tenant);
      if (!normalizedTenant) continue;
      const values = Array.isArray(surfaceValue)
        ? surfaceValue.map((entry) => String(entry))
        : String(surfaceValue)
            .split(',')
            .map((entry) => entry.trim());
      const flags: Set<SubmodelSurface> = new Set();
      for (const value of values) {
        const normalized = normalizeTenant(value);
        if (normalized === 'publisher' || normalized === 'editor' || normalized === 'viewer') {
          flags.add(normalized);
        }
      }
      result[normalizedTenant] = flags;
    }
    return result;
  } catch {
    return {};
  }
}

function localOverride(tenant: string): SubmodelSurfaceFlags | null {
  if (typeof window === 'undefined') return null;
  const raw = window.localStorage.getItem('dpp.submodelUxRollout.override');
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const tenantOverride = parsed[tenant];
    if (!tenantOverride || typeof tenantOverride !== 'object') return null;
    const record = tenantOverride as Record<string, unknown>;
    return {
      publisher: record.publisher !== false,
      editor: record.editor !== false,
      viewer: record.viewer !== false,
    };
  } catch {
    return null;
  }
}

export function resolveSubmodelUxRollout(tenantSlug: string): SubmodelUxRollout {
  const tenant = normalizeTenant(tenantSlug);
  const globallyEnabled = parseBoolean(import.meta.env.VITE_SUBMODEL_UX_ENABLED, true);
  const globalSurfaces = parseSurfaceCsv(import.meta.env.VITE_SUBMODEL_UX_SURFACES);
  const canaryTenants = parseCsv(
    import.meta.env.VITE_SUBMODEL_UX_CANARY_TENANTS,
    DEFAULT_CANARY_TENANTS,
  );
  const forceEnabledTenants = parseCsv(import.meta.env.VITE_SUBMODEL_UX_FORCE_ENABLE_TENANTS);
  const forceDisabledTenants = parseCsv(import.meta.env.VITE_SUBMODEL_UX_FORCE_DISABLE_TENANTS);
  const tenantOverrides = parseTenantOverrides(import.meta.env.VITE_SUBMODEL_UX_TENANT_SURFACES);

  const effectiveEnabled =
    (globallyEnabled && !canaryTenants.size) ||
    forceEnabledTenants.has(tenant) ||
    (globallyEnabled && canaryTenants.has(tenant));

  const overridden = localOverride(tenant);
  if (overridden) {
    return {
      tenant,
      enabled: true,
      isCanaryTenant: canaryTenants.has(tenant),
      source: 'override',
      surfaces: overridden,
    };
  }

  if (!effectiveEnabled || forceDisabledTenants.has(tenant)) {
    return {
      tenant,
      enabled: false,
      isCanaryTenant: canaryTenants.has(tenant),
      source: 'global',
      surfaces: {
        publisher: false,
        editor: false,
        viewer: false,
      },
    };
  }

  const tenantSurfaceOverride = tenantOverrides[tenant];
  const baseSurfaces = tenantSurfaceOverride ?? globalSurfaces;

  return {
    tenant,
    enabled: true,
    isCanaryTenant: canaryTenants.has(tenant),
    source: canaryTenants.has(tenant) ? 'canary' : 'global',
    surfaces: {
      publisher: baseSurfaces.has('publisher'),
      editor: baseSurfaces.has('editor'),
      viewer: baseSurfaces.has('viewer'),
    },
  };
}
