# Security & Tenancy Inspection Report

**Inspector**: Security/Tenancy Engineer
**Date**: 2026-02-10
**Scope**: Multi-tenant isolation, RLS policies, ABAC enforcement, SSRF, SQL injection vectors, public endpoint security

---

## Executive Summary

The platform's multi-tenant isolation is **well-implemented** with defense-in-depth: application-level `tenant_id` filtering in all service queries PLUS PostgreSQL Row-Level Security (RLS) policies on all tenant-scoped tables. No critical or high-severity findings. The security hardening from PRs #52 and #54 is verified and effective.

**Overall Risk Rating: LOW**

---

## 1. Row-Level Security (RLS) Coverage

### Tables WITH RLS (all using `tenant_id = current_setting('app.current_tenant', true)::uuid`)

| Migration | Tables |
|-----------|--------|
| 0005 | `dpps`, `dpp_revisions`, `encrypted_values`, `policies`, `connectors`, `audit_events` |
| 0008 | `dpp_masters`, `dpp_master_versions` |
| 0009 | `dpp_master_aliases` |
| 0022 | `audit_merkle_roots`, `compliance_reports`, `edc_asset_registrations`, `thread_events`, `lca_calculations`, `epcis_events`, `epcis_named_queries`, `webhook_subscriptions`, `resolver_links`, `shell_descriptors`, `asset_discovery_mappings`, `issued_credentials` |

**Total: 18 tenant-scoped tables with RLS** -- all tables using `TenantScopedMixin` are covered.

### Tables WITHOUT RLS (by design)

| Table | Reason | Risk |
|-------|--------|------|
| `templates` | Platform-wide shared resource (no `tenant_id` column, not `TenantScopedMixin`). Templates are fetched from IDTA GitHub and shared across all tenants. | NONE |
| `users` | Platform-wide user records. User-tenant mapping is via `tenant_members`. | NONE |
| `platform_settings` | Platform-wide configuration. Admin-only access. | NONE |
| `tenants` | The tenant table itself. No isolation needed. | NONE |
| `tenant_members` | Has `tenant_id` FK but no RLS. Lookups use explicit `tenant_id` filtering in `tenancy.py`. | NONE |
| `webhook_delivery_log` | Not tenant-scoped directly. Linked via `subscription_id` FK to `webhook_subscriptions` (which HAS RLS). | NONE |

### RLS Activation Mechanism

`tenancy.py:81-84`: Sets `app.current_tenant` session variable on every authenticated request:
```python
await db.execute(
    text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
    {"tenant_id": str(tenant.id)},
)
```

Platform admins get RLS bypass via `SET LOCAL ROLE` with regex-validated role name:
```python
if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", role):
    await db.execute(text(f'SET LOCAL ROLE "{role}"'))
```

**Verdict: PASS** -- All tenant-scoped tables have RLS. Non-tenant tables are correctly excluded.

---

## 2. Tenant ID Scoping in Queries

### DPP Service (`dpps/service.py`) -- ALL PASS

| Method | Filter | Status |
|--------|--------|--------|
| `get_dpp()` | `DPP.tenant_id == tenant_id` | PASS |
| `get_dpp_by_slug()` | `DPP.tenant_id == tenant_id` | PASS |
| `get_dpps_for_owner()` | `DPP.tenant_id == tenant_id` | PASS |
| `get_dpps_for_tenant()` | `DPP.tenant_id == tenant_id` | PASS |
| `count_dpps_for_tenant()` | `DPP.tenant_id == tenant_id` | PASS |
| `get_published_dpps()` | `DPP.tenant_id == tenant_id` | PASS |
| `find_existing_dpp()` | `DPP.tenant_id == tenant_id` | PASS |
| `get_latest_revision()` | `DPPRevision.tenant_id == tenant_id` | PASS |
| `get_published_revision()` | `DPPRevision.tenant_id == tenant_id` | PASS |
| `get_revision_by_no()` | `DPPRevision.tenant_id == tenant_id` | PASS |
| `_cleanup_old_draft_revisions()` | `DPPRevision.tenant_id == tenant_id` | PASS |
| `update_submodel()` | Via `get_dpp(dpp_id, tenant_id)` | PASS |
| `publish_dpp()` | Via `get_dpp(dpp_id, tenant_id)` | PASS |
| `archive_dpp()` | Via `get_dpp(dpp_id, tenant_id)` | PASS |
| `create_dpp()` | Sets `tenant_id=tenant_id` on new record | PASS |
| `create_dpp_from_environment()` | Sets `tenant_id=tenant_id` on new record | PASS |

### DPP Router (`dpps/router.py`) -- ALL PASS

| Endpoint | Auth | Tenant Check | ABAC Check |
|----------|------|-------------|------------|
| `POST /dpps` | `TenantPublisher` | `tenant.tenant_id` | `require_access(create)` |
| `POST /dpps/batch-import` | `TenantPublisher` | `tenant.tenant_id` | `require_access(create)` |
| `POST /dpps/import` | `TenantPublisher` | `tenant.tenant_id` | `require_access(create)` |
| `POST /dpps/rebuild-all` | `TenantAdmin` | `tenant.tenant_id` | N/A (admin-only) |
| `GET /dpps` | `TenantContextDep` | `tenant.tenant_id` | `check_access(list)` per DPP |
| `GET /dpps/{id}` | `TenantContextDep` | `tenant.tenant_id` | `require_access(read)` |
| `GET /dpps/by-slug/{slug}` | `TenantContextDep` | `tenant.tenant_id` | `require_access(read)` |
| `PUT /dpps/{id}/submodel` | `TenantPublisher` | `tenant.tenant_id` + ownership check | `require_access(update)` |
| `POST /dpps/{id}/publish` | `TenantPublisher` | `tenant.tenant_id` + ownership check | `require_access(publish)` |
| `POST /dpps/{id}/archive` | `TenantPublisher` | `tenant.tenant_id` + ownership check | `require_access(archive)` |
| `GET /dpps/{id}/revisions` | `TenantPublisher` | `tenant.tenant_id` + ownership check | N/A |
| `GET /dpps/{id}/diff` | `TenantPublisher` | `tenant.tenant_id` + ownership check | N/A |

### Resolver Service (`resolver/service.py`) -- ALL PASS
All CRUD and query methods accept and filter by `tenant_id`.

### Templates Service (`templates/service.py`)
No tenant scoping -- templates are platform-wide shared resources. **Correct by design.**

**Verdict: PASS** -- All tenant-scoped operations consistently filter by `tenant_id`.

---

## 3. Cross-Tenant Isolation

### Tenant Context Resolution (`tenancy.py`)

- Non-member access returns HTTP 403 "User is not a member of this tenant" -- **PASS**
- Auto-provisioning gated: only for `default` tenant + `development` environment + `auto_provision_default_tenant=True` -- **PASS**
- Production validator enforces `auto_provision_default_tenant=False` -- **PASS**
- Inactive tenants return HTTP 403 "Tenant is inactive" -- **PASS**
- Tenant slug is normalized (`strip().lower()`) -- **PASS**

### Object Creation Tenant Binding

All created objects (`DPP`, `DPPRevision`, etc.) receive `tenant_id` from the authenticated tenant context, not from user input. No endpoint allows a user to specify a different `tenant_id`.

**Verdict: PASS** -- Proper cross-tenant isolation at both application and database layers.

---

## 4. OPA Policy Enforcement

| Check | Status |
|-------|--------|
| `opa_enabled` defaults to `True` | PASS |
| Production validator requires `opa_enabled=True` | PASS (`config.py:447`) |
| OPA client fails closed on timeout | PASS (returns `PolicyEffect.DENY`) |
| OPA client fails closed on HTTP error | PASS (returns `PolicyEffect.DENY`) |
| All DPP CRUD calls `require_access()` or `check_access()` | PASS |
| ABAC context includes `tenant_id`, `tenant_slug`, user roles | PASS |
| Platform roles (`admin`, `auditor`) merged with tenant roles | PASS |

**Verdict: PASS** -- OPA enforcement is mandatory in production and fails closed.

---

## 5. SQL Injection Vectors

### Template Ingestion

| Vector | Analysis | Status |
|--------|----------|--------|
| Semantic IDs | Hardcoded in `catalog.py`, not user-controlled | SAFE |
| Template JSON from GitHub | Stored as JSONB via parameterized SQLAlchemy queries | SAFE |
| `idShort` values | From template data, stored in JSONB column | SAFE |
| `format()` calls in `service.py:551,719` | Build file URLs, not SQL | SAFE |

### Dynamic SQL

| Location | Code | Risk |
|----------|------|------|
| `tenancy.py:82` | `set_config('app.current_tenant', :tenant_id, true)` | SAFE -- parameterized |
| `tenancy.py:90` | `SET LOCAL ROLE "{role}"` | SAFE -- regex-validated `[A-Za-z_][A-Za-z0-9_]*` |
| `audit.py:137` | `pg_advisory_xact_lock(hashtext(:tid))` | SAFE -- parameterized |

### f-string SQL pattern (highest risk)

The `SET LOCAL ROLE` on `tenancy.py:90` uses f-string interpolation with `text()`, which is the most dangerous pattern. However, the preceding regex validation (`re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", role)`) limits the value to alphanumeric + underscore, AND the value comes from `settings.db_admin_role` (not user input), making exploitation impossible.

**Verdict: PASS** -- No SQL injection vectors found.

---

## 6. Public Endpoint Security

### DPP Public Router (`dpps/public_router.py`)

| Check | Status |
|-------|--------|
| Tenant resolved by slug with active status check | PASS |
| Only `DPPStatus.PUBLISHED` DPPs served | PASS |
| Queries filter by `DPP.tenant_id == tenant.id` | PASS |
| Published revision query filters by `DPPRevision.tenant_id == dpp.tenant_id` | PASS |
| Confidentiality-based element filtering applied | PASS |
| ESPR tier filtering applied with `in_place=True` | PASS |
| No `owner_subject` in public response model | PASS |

### EPCIS Public Router (`epcis/public_router.py`)

| Check | Status |
|-------|--------|
| Tenant resolved by slug with active status check | PASS |
| Only published DPPs served (`DPP.status == DPPStatus.PUBLISHED`) | PASS |
| Events filtered by `EPCISEvent.tenant_id == tenant.id` | PASS |
| Result capped at 100 events (`MAX_PUBLIC_EVENTS`) | PASS |
| Uses `PublicEPCISEventResponse` (excludes `created_by_subject`, `created_at`) | PASS |

### Resolver Public Router (`resolver/public_router.py`)

| Check | Status |
|-------|--------|
| Open redirect prevention (`parsed.scheme in ("http", "https")`) | PASS |
| Linkset response includes proper `Cache-Control` headers | PASS |
| GS1 resolver description document exposes no tenant data | PASS |
| Cross-tenant resolution by design (GS1 identifiers are globally unique) | INFO |

**Verdict: PASS** -- Public endpoints properly scope data and exclude sensitive fields.

---

## 7. SSRF Protection

### Resolver Schemas (`resolver/schemas.py`)

| Check | Status |
|-------|--------|
| `ResolverLinkCreate.href` validates scheme (http/https only) | PASS |
| `ResolverLinkUpdate.href` validates scheme (http/https only) | PASS |
| Both create AND update paths protected | PASS |

### Webhook Schemas (`webhooks/schemas.py`)

| Check | Status |
|-------|--------|
| `WebhookCreate.url` validates via `_reject_internal_urls()` | PASS |
| `WebhookUpdate.url` validates via `_reject_internal_urls()` | PASS |
| Blocks: localhost, 127.x, 10.x, 172.16-31.x, 192.168.x, 169.254.x | PASS |
| Blocks: ::1, fe80:, fd/fc private IPv6 | PASS |
| Uses `ipaddress.ip_address()` as secondary check | PASS |

**Verdict: PASS** -- SSRF protection on both create and update paths.

---

## 8. Additional Security Checks

### JWT/OIDC Validation (`security/oidc.py`)

| Check | Status |
|-------|--------|
| Native PyJWT `verify_iss=True` with allowed issuers list | PASS |
| Manual defense-in-depth issuer check after decode | PASS |
| `InvalidIssuerError` handled separately (no info leakage) | PASS |
| `azp` claim validated against allowed client IDs | PASS |
| Fallback to `aud` claim when `azp` absent | PASS |
| JWKS cache with 1-hour TTL + on-demand refresh | PASS |

### Metrics Authentication (`main.py`)

| Check | Status |
|-------|--------|
| Dev without token: unauthenticated (convenience) | PASS |
| Production without token: 404 (hides endpoint) | PASS |
| Production with token: `hmac.compare_digest()` (constant-time) | PASS |

### DPP Lifecycle State Guards (`dpps/service.py`)

| Guard | Status |
|-------|--------|
| Cannot update archived DPP | PASS (`service.py:587`) |
| Cannot publish archived DPP | PASS (`service.py:726`) |
| Cannot archive draft DPP | PASS (`service.py:843`) |
| Cannot archive already-archived DPP | PASS (`service.py:845`) |

### Error Sanitization

| Location | Status |
|----------|--------|
| `router.py:252`: Generic "DPP creation failed due to an internal error" | PASS |
| DPP service errors: `ValueError` with controlled messages | PASS |
| No `f"... {exc}"` in generic exception handlers | PASS |

### ESPR Tier Deny-by-Default (`submodel_filter.py`)

| Check | Status |
|-------|--------|
| `None`/empty/whitespace tier defaults to `"consumer"` | PASS |
| Unknown tier gets `frozenset()` (empty = no access) | PASS |
| Missing semantic ID returns `False` (denied) | PASS |
| `manufacturer` and `market_surveillance_authority` get full access | PASS |

### Audit Hash Chain Integrity (`audit.py`)

| Check | Status |
|-------|--------|
| `pg_advisory_xact_lock(hashtext(:tid))` per tenant | PASS |
| Platform events use fixed lock key `0` | PASS |
| Transaction-scoped (auto-release on commit/rollback) | PASS |
| Genesis hash for first event in chain | PASS |

---

## 9. Informational Findings

### FINDING-1 (INFO): Cross-Tenant Resolver Resolution

The public resolver (`/api/v1/resolve/01/{gtin}...`) resolves identifiers across ALL tenants since GS1 Digital Link identifiers are globally unique. This is correct for GS1 compliance but means:
- Tenant A can discover that an identifier registered by Tenant B exists
- The resolved URL reveals the target DPP endpoint

**Risk**: LOW -- GS1 identifiers are designed to be publicly resolvable. The resolver returns URLs that point to tenant-scoped public endpoints which enforce their own access controls.

### FINDING-2 (INFO): `webhook_delivery_log` Indirect Tenant Scoping

The `webhook_delivery_log` table has no direct `tenant_id` or RLS. It's accessed through `webhook_subscriptions` (which has RLS). The relationship cascade ensures deletion propagation.

**Risk**: NONE -- Access is only through the parent subscription which has RLS.

---

## 10. Conclusion

The platform demonstrates strong multi-tenant security with:

1. **Defense-in-depth**: Application-level `tenant_id` filtering + PostgreSQL RLS + OPA ABAC
2. **Fail-closed defaults**: OPA denies on timeout/error, ESPR denies unknown tiers
3. **Comprehensive SSRF protection**: Both create and update paths validate URLs
4. **Proper JWT validation**: Dual-layer issuer verification + azp/aud claim checking
5. **Production safeguards**: Config validators enforce security settings at startup

No critical, high, or medium severity findings. The architecture correctly separates platform-wide resources (templates, users) from tenant-scoped data (DPPs, revisions, events).
