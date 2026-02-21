# CEN prEN Rollout Guide (18219/18220/18222)

This runbook covers safe rollout of the CEN draft compliance layer.

## 1. Deploy migrations with CEN disabled

Keep CEN feature flags off while applying schema changes:

- `CEN_DPP_ENABLED=false`
- Keep existing routes and behavior unchanged during migration.

Apply migrations:

```bash
cd backend
uv run alembic upgrade head
```

## 2. Run identifier/carrier backfill

Backfill canonical identifiers for existing DPPs and link/hash carriers where possible.

Dry run first:

```bash
cd backend
uv run python tools/backfill_cen_identifiers.py --all-tenants --dry-run
```

Apply changes:

```bash
cd backend
uv run python tools/backfill_cen_identifiers.py --all-tenants
```

Optional scope controls:

- `--tenant-id <uuid>`
- `--limit-per-tenant <n>`
- `--skip-carrier-linking`

## 3. Enable in staging

Enable CEN in staging only after migration + backfill:

- `CEN_DPP_ENABLED=true`
- `CEN_PROFILE_18219=prEN18219:2025-07`
- `CEN_PROFILE_18220=prEN18220:2025-07`
- `CEN_PROFILE_18222=prEN18222:2025-07`
- `CEN_ALLOW_HTTP_IDENTIFIERS=false` (recommended default)

Run validation suites in staging:

```bash
cd backend
uv run pytest tests/unit/test_cen_api_openapi.py tests/unit/test_cen_api_service.py tests/unit/test_data_carrier_cen.py -q
```

## 4. Production phased enablement

Roll out in this order:

1. Enable CEN read/search facade routes first.
2. Monitor CEN route usage and validation errors.
3. Enable strict publish identifier gate and supersede enforcement after backfill verification.
4. Enable DataMatrix rendering only on runtimes where dependency health checks pass.

## 5. Operational checks

Confirm:

- CEN routes return `X-Standards-Profile` header.
- Public CEN endpoints return published-only filtered payloads.
- DataMatrix render returns deterministic `501` when dependency is unavailable.
- Backfill summary shows no unexpected tenant errors.
