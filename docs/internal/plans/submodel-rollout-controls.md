# Submodel UX Rollout Controls

## Purpose
This document defines Phase 5 rollout controls for redesigned submodel UX surfaces.

## Scope
Controls apply to:
1. Publisher submodel aggregation (`publisher`)
2. Submodel editor UX enhancements (`editor`)
3. Public viewer advanced/raw submodel UX (`viewer`)

## Environment Flags
Configured via frontend runtime environment:

1. `VITE_SUBMODEL_UX_ENABLED`
- Global master switch (`true` / `false`)

2. `VITE_SUBMODEL_UX_SURFACES`
- Comma-separated enabled surfaces globally
- Default: `publisher,editor,viewer`

3. `VITE_SUBMODEL_UX_CANARY_TENANTS`
- Comma-separated tenant slugs allowed for rollout when canarying
- If non-empty, rollout is limited to this list (unless force-enabled)

4. `VITE_SUBMODEL_UX_FORCE_ENABLE_TENANTS`
- Comma-separated tenant slugs always enabled

5. `VITE_SUBMODEL_UX_FORCE_DISABLE_TENANTS`
- Comma-separated tenant slugs always disabled

6. `VITE_SUBMODEL_UX_TENANT_SURFACES`
- JSON map of tenant to per-surface allowlist
- Example:
```json
{"tenant-a":["publisher","viewer"],"tenant-b":["editor"]}
```

## Local Override (debug/canary verification)
Local browser override key:
- `localStorage['dpp.submodelUxRollout.override']`

Example value:
```json
{
  "default": {
    "publisher": true,
    "editor": false,
    "viewer": true
  }
}
```

## Resolution Order
1. Local override (`dpp.submodelUxRollout.override`)
2. Force enable / force disable tenant lists
3. Global enabled + canary tenant allowlist
4. Tenant surface override map, else global surface set

## Current Wiring
1. Publisher page uses rollout to gate advanced filter/sort UI.
2. Editor page uses rollout to gate section-progress panel and destructive rebuild dialog.
3. Viewer page uses rollout to gate advanced raw submodel mode.

## Backend Operational Guardrails
1. `POST /dpps/{dpp_id}/submodels/refresh-rebuild` is single-flight per DPP.
- PostgreSQL deploys use advisory transaction lock (`pg_try_advisory_xact_lock`).
- Non-Postgres dev/test backends use in-process locking as fallback.
- Concurrent calls return `409 Conflict`.

2. `refresh-rebuild` remains mutation-protected.
- Only DPP owner or tenant admin can invoke.
- `dpp.access` update permission is still required server-side.

3. `dpp_admin_bypass` is break-glass only.
- Keep role assignment out of runtime service accounts and Keycloak default mappings.
- Require audited, time-bound operational elevation for emergency use.
