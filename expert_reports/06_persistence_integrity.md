# Phase 3a: DPP Persistence Integrity Report

**Inspector**: persistence-integrity
**Date**: 2026-02-10
**Scope**: DPP lifecycle persistence, template provenance, state machine, revision history, RLS tenant isolation
**Status**: COMPLETE

---

## Executive Summary

The DPP persistence layer demonstrates **strong integrity** across all inspected dimensions. The state machine guards (PR #52), template provenance propagation (PR #45/47/48), and revision history management are correctly implemented. RLS tenant isolation covers all 21 tenant-scoped tables across 4 migrations. One medium-severity finding was identified related to draft revision cleanup race conditions, plus several informational observations.

**Overall Assessment**: **PASS** (1 medium, 2 low, 4 informational findings)

---

## 1. Template Provenance Integrity

### 1.1 Provenance Capture Paths

All 5 DPP creation/mutation paths correctly handle `template_provenance`:

| Path | Location | Provenance Source | Null-Safety | Verdict |
|------|----------|-------------------|-------------|---------|
| `create_dpp()` | service.py:144-155 | `_build_template_provenance(selected_templates)` | N/A (fresh build) | **PASS** |
| `create_dpp_from_environment()` | service.py:226 | `template_provenance={}` (hardcoded empty) | N/A | **PASS** |
| `update_submodel()` | service.py:644 | `current_revision.template_provenance or {}` | `or {}` | **PASS** |
| `publish_dpp()` (new rev) | service.py:759 | `latest_revision.template_provenance or {}` | `or {}` | **PASS** |
| `_rebuild_dpp_from_templates()` | service.py:817 | `_build_provenance_from_db_templates(templates)` | Fresh build | **PASS** |

### 1.2 Provenance Schema

`_build_template_provenance()` (service.py:889-913) produces per-key entries with:
- `idta_version`: From catalog descriptor (always present) — `"{major}.{minor}"` format
- `semantic_id`: From catalog descriptor (always present)
- `resolved_version`: From DB Template record (None if not yet fetched)
- `source_file_sha`: From DB Template record (None if not yet fetched)
- `source_file_path`: From DB Template record (None if not yet fetched)
- `source_kind`: From DB Template record (None if not yet fetched)
- `selection_strategy`: From DB Template record (None if not yet fetched)

**Observation**: On first-run or offline scenarios, provenance contains the template key with `idta_version` and `semantic_id` populated, but source fields as `None`. This is expected behavior — provenance improves after first template refresh.

### 1.3 Rebuild Provenance (PR #48 Fix Verified)

`_rebuild_dpp_from_templates()` (service.py:817) uses `_build_provenance_from_db_templates()` which computes **fresh** provenance from current Template DB objects — not copying stale provenance from the old revision. This was the BUG-2 fix from PR #48.

`_build_provenance_from_db_templates()` (service.py:915-935) iterates Template objects and falls back to `tmpl.idta_version` when no catalog descriptor exists, which is correct for templates that may have been removed from catalog.

### 1.4 Existing Test Coverage

- `test_dpp_provenance_paths.py`: 5 tests covering create, import, update (null→empty, existing→preserved), rebuild, publish provenance propagation
- `test_templates_router_contract.py`: Validates `_build_template_response()` fields
- E2E pipeline (`test_dpp_pipeline.py`): Checks provenance in created DPP

**Verdict**: Provenance integrity is **SOLID**. All 5 mutation paths are covered and null-safe.

---

## 2. State Machine Guards

### 2.1 Lifecycle: DRAFT → PUBLISHED → ARCHIVED

| Transition | Guard | Location | Error Message |
|-----------|-------|----------|--------------|
| DRAFT → PUBLISHED | Allowed | service.py:705-782 | — |
| PUBLISHED → PUBLISHED | Creates new published revision | service.py:747-762 | — |
| DRAFT → ARCHIVED | **Blocked** | service.py:842-843 | "Cannot archive a draft DPP — publish it first" |
| ARCHIVED → PUBLISHED | **Blocked** | service.py:725-726 | "Cannot publish an archived DPP" |
| ARCHIVED → Updated | **Blocked** | service.py:586-587 | "Cannot update an archived DPP" |
| ARCHIVED → ARCHIVED | **Blocked** | service.py:844-845 | "DPP is already archived" |

### 2.2 Guard Analysis

**Correctness**: All 4 invalid transitions are blocked with descriptive ValueError messages. The guards are **in-memory enum checks** (no DB overhead).

**Intentional Design**: A PUBLISHED DPP CAN be updated (`update_submodel` only blocks ARCHIVED, not PUBLISHED). This creates a new DRAFT revision, which is the intended edit-after-publish workflow for subsequent versions.

**Compliance Gate**: `publish_dpp()` includes optional ESPR compliance pre-check (service.py:729-737) gated by `compliance_check_on_publish` setting. Blocks publish on critical violations.

### 2.3 Missing Guard: Double-Publish Idempotency

When `publish_dpp()` is called on an already-published DPP (latest revision is `RevisionState.PUBLISHED`), it creates a **new revision** with the same content (service.py:747-762). This is by design for re-signing, but means repeated publish calls increment revision count without data changes.

**Verdict**: State machine is **CORRECT**. All invalid transitions are blocked.

---

## 3. Revision History Integrity

### 3.1 Monotonic Revision Numbers

Every mutation increments `revision_no` by 1 from the latest revision:
- `create_dpp()`: Sets `revision_no=1` (service.py:148)
- `update_submodel()`: `current_revision.revision_no + 1` (service.py:634)
- `publish_dpp()` (new rev): `latest_revision.revision_no + 1` (service.py:749)
- `_rebuild_dpp_from_templates()`: `current_revision.revision_no + 1` (service.py:812)

**Database Constraint**: `UniqueConstraint("dpp_id", "revision_no", name="uq_dpp_revision_no")` (models.py:497) prevents duplicate revision numbers per DPP.

### 3.2 Content Digest

`_calculate_digest()` produces SHA-256 of canonicalized JSON. Computed at:
- DPP creation (service.py:123)
- Submodel update (service.py:633)
- DPP import (service.py:200)

**Published revisions** also get `signed_jws` (JWS signature of the digest) for tamper-evidence. Draft revisions have `signed_jws=None`.

### 3.3 Draft Cleanup

`_cleanup_old_draft_revisions()` (service.py:854-872):
- Keeps most recent `dpp_max_draft_revisions` (default: 10) drafts
- Only deletes DRAFT state revisions (published revisions are always kept)
- Called after `update_submodel()` and `_rebuild_dpp_from_templates()`

### 3.4 Revision Ordering

`DPP.revisions` relationship uses `order_by="DPPRevision.revision_no.desc()"` (models.py:414) — latest revision first. `get_latest_revision()` queries with `.order_by(DPPRevision.revision_no.desc()).limit(1)` (service.py:394-400).

**Verdict**: Revision history integrity is **STRONG**. Monotonic numbering + DB constraints + digest chain.

---

## 4. RLS Tenant Isolation

### 4.1 Policy Coverage

All tenant-scoped tables have RLS policies across 4 migrations:

| Migration | Tables | Count |
|-----------|--------|-------|
| 0005_tenant_rls | dpps, dpp_revisions, encrypted_values, policies, connectors, audit_events | 6 |
| 0008_dpp_masters | dpp_masters, dpp_master_versions | 2 |
| 0009_master_aliases | dpp_master_aliases | 1 |
| 0022_complete_tenant_rls | audit_merkle_roots, compliance_reports, edc_asset_registrations, thread_events, lca_calculations, epcis_events, epcis_named_queries, webhook_subscriptions, resolver_links, shell_descriptors, asset_discovery_mappings, issued_credentials | 12 |
| **Total** | | **21** |

### 4.2 Policy Pattern

All policies use identical pattern:
```sql
CREATE POLICY {table}_tenant_isolation
ON {table}
USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
```

**Fail-Closed**: The `true` parameter to `current_setting()` means missing setting returns empty string, which fails the UUID cast, resulting in **zero rows returned**. This is safe behavior.

### 4.3 Tables WITHOUT RLS (By Design)

The following tables are intentionally NOT tenant-scoped:
- `tenants` — tenant metadata itself
- `tenant_members` — cross-tenant membership lookup
- `users` — global user identities
- `platform_settings` — platform-level configuration
- `templates` / `template_source_metadata` — shared template cache

### 4.4 RLS + Application-Level Checks

The DPP service applies **double isolation**:
1. **RLS** (database level): Filters rows by `current_setting('app.current_tenant')`
2. **Application queries** (service level): Every query includes `WHERE tenant_id = :tenant_id`

This provides defense-in-depth — even if RLS is misconfigured, the application-level tenant_id filter prevents cross-tenant access.

**Verdict**: RLS coverage is **COMPLETE** for all tenant-scoped tables.

---

## 5. Batch Import Integrity

### 5.1 Savepoint Isolation

`batch_import_dpps()` (router.py:307-360) uses per-item savepoints:
```python
async with db.begin_nested():
    dpp = await service.create_dpp(...)
```

One item's failure does not roll back others — correct use of PostgreSQL savepoints.

### 5.2 Error Sanitization

Failed imports return generic `"Import failed"` message (router.py:338) — no internal exception details leaked. The `exc_info=True` flag in `logger.warning` ensures the full traceback is logged server-side for debugging.

### 5.3 Provenance in Batch Import

Batch import calls `service.create_dpp()` which builds provenance via `_build_template_provenance()`. Provenance is correctly captured for each batch item.

### 5.4 Limit Enforcement

`BatchImportRequest.dpps` has `max_length=100` (router.py:171). Validated by Pydantic before reaching the handler.

**Verdict**: Batch import is **CORRECT** with proper isolation, error handling, and provenance.

---

## 6. Edge Case Analysis

### 6.1 Empty Collections

The basyx_builder (basyx_builder.py:528-532) handles `SubmodelElementCollection` with empty children:
```python
instance = model.SubmodelElementCollection(
    id_short=None,
    value=[
        self._instantiate_element(child, value.get(child.id_short))
        for child in element.value
    ]
)
```
When `element.value` (template elements) is empty or `value.get(child.id_short)` returns None for all children, this produces a collection with default/empty values. The JSONB column stores this faithfully.

### 6.2 MultiLanguageProperty

Handled at basyx_builder.py:360, 435, 521-522. Multi-language values are stored as `langStringSet` in the AAS environment JSONB. The fixture `edge_case_multilang` tests 6 languages (en, de, fr, es, it, ja).

### 6.3 Missing Optional Fields

`initial_data` defaults to `None` / `{}` in both `create_dpp()` and `create_dpp_from_environment()`. The template builder creates the structural tree regardless — missing fields get default/empty values from the template.

### 6.4 Concurrent Revision Creation

No advisory locks on DPP revision creation. If two users update the same DPP simultaneously:
- Both read the same `current_revision.revision_no` (e.g., 5)
- Both try to create revision 6
- `uq_dpp_revision_no` constraint catches the collision → one fails with IntegrityError

**Mitigation**: The application doesn't serialize concurrent DPP updates. The database constraint provides crash consistency, but the losing request gets a 500 error rather than a graceful retry. This is acceptable for the typical single-publisher-per-DPP use case.

---

## 7. Findings Register

### FINDING-1: Draft Cleanup Race Condition (Medium)

**Location**: `service.py:854-872`
**Description**: `_cleanup_old_draft_revisions` runs after `update_submodel` and `_rebuild_dpp_from_templates` without advisory locks. Concurrent updates could interleave cleanup with revision creation.
**Impact**: Minor — could keep 1-2 extra draft revisions beyond the limit, or in extreme cases, delete a draft being created concurrently.
**Risk**: LOW (single-publisher-per-DPP is the typical use case)
**Recommendation**: Consider adding `pg_advisory_xact_lock` on the DPP ID during update + cleanup, similar to the audit hash chain pattern.

### FINDING-2: Double-Publish Creates Redundant Revisions (Low)

**Location**: `service.py:747-762`
**Description**: Calling `publish_dpp()` on an already-published DPP creates a new revision with identical content. This increments revision count without meaningful change.
**Impact**: Revision history inflation; no functional impact.
**Recommendation**: Consider adding an idempotency check (compare digest of latest published revision vs current).

### FINDING-3: Import DPPs Have Empty Provenance (Informational)

**Location**: `service.py:226`
**Description**: `create_dpp_from_environment()` sets `template_provenance={}`. Imported DPPs therefore have no template traceability.
**Impact**: Expected behavior — imported DPPs come from external sources without template context.
**Recommendation**: Document this as expected behavior in API docs.

### FINDING-4: Revision Collision Returns 500 (Informational)

**Location**: Concurrent `update_submodel()` calls
**Description**: Concurrent updates to the same DPP can trigger `uq_dpp_revision_no` constraint violation, resulting in an unhandled IntegrityError (500).
**Impact**: Low — single-publisher-per-DPP is the typical use case.
**Recommendation**: Could catch `IntegrityError` and retry with incremented revision number, or add optimistic locking.

### FINDING-5: RLS Fail-Closed Verified (Informational)

**Location**: Migrations 0005, 0008, 0009, 0022
**Description**: RLS policy `current_setting('app.current_tenant', true)::uuid` correctly fails closed (empty string → UUID cast failure → no rows). Verified across all 21 tenant-scoped tables.
**Impact**: None — this is correct behavior.

### FINDING-6: Digest Is Not Globally Unique (Informational)

**Location**: `service.py:_calculate_digest()`
**Description**: SHA-256 digest is computed per-revision from AAS environment JSON. Two DPPs with identical content produce identical digests. The digest is not used as a unique key, only for integrity verification and signing.
**Impact**: None — digests are per-revision, not globally unique identifiers.

---

## 8. Test DPP Scenarios

### 8.1 Fixture File

Located at: `backend/tests/fixtures/inspection_dpps.json`

Contains 8 test DPP configurations:
| ID | Template(s) | Purpose |
|----|-------------|---------|
| minimal_nameplate | digital-nameplate | Minimal required fields |
| full_nameplate | digital-nameplate | All optional fields, multilang |
| carbon_footprint | carbon-footprint | PCF data |
| technical_data | technical-data | Technical properties |
| hierarchical_structures | hierarchical-structures | BOM structures |
| battery_passport | battery-passport | EU battery regulation (experimental template) |
| edge_case_empty_collections | hierarchical-structures | Empty component list |
| edge_case_multilang | digital-nameplate | 6 languages (en, de, fr, es, it, ja) |

### 8.2 Lifecycle Scenarios Verified (Code Review)

| Scenario | Expected | Code Location | Verified |
|----------|----------|---------------|----------|
| Create → Draft | Status=DRAFT, rev=1 | service.py:126-157 | YES |
| Update → New Rev | rev+1, provenance carried | service.py:634-657 | YES |
| Publish → Published | Status=PUBLISHED, JWS signed | service.py:705-782 | YES |
| Archive → Archived | Status=ARCHIVED, immutable | service.py:831-852 | YES |
| Draft → Archive | BLOCKED | service.py:842-843 | YES |
| Archived → Update | BLOCKED | service.py:586-587 | YES |
| Archived → Publish | BLOCKED | service.py:725-726 | YES |
| Archived → Archive | BLOCKED | service.py:844-845 | YES |

---

## 9. DPP IDs for Phase 3b Export Testing

See `created_dpps.json` for structured DPP metadata. Test DPPs use the fixture definitions from `inspection_dpps.json` and target these template combinations:

1. **Single-template DPPs**: digital-nameplate, battery-passport, hierarchical-structures
2. **Multi-template DPPs**: digital-nameplate + technical-data + contact-information
3. **Edge cases**: Empty collections, multilingual content (6 languages)

Each DPP should be created via the DPP service's `create_dpp()` method during E2E testing to verify:
- Provenance is populated with template metadata
- AAS environment is correctly structured
- Export formats (AASX, JSON, JSON-LD, Turtle) can round-trip the content

---

## 10. Conclusion

The DPP persistence layer is well-architected with:
- **Provenance**: Complete propagation across all 5 mutation paths with null-safety
- **State machine**: All 4 invalid lifecycle transitions blocked at service level
- **Revision history**: Monotonic numbering, DB uniqueness constraint, published revision preservation
- **RLS**: 21 tables covered, fail-closed policy, defense-in-depth with application-level checks
- **Batch import**: Per-item savepoint isolation, sanitized errors, correct provenance capture

The medium finding (draft cleanup race condition) has low real-world impact due to single-publisher-per-DPP usage patterns. All other findings are low/informational.
