# Inspection Report: Template Provenance & Versioning

**Inspector**: Template Versioning Engineer
**Date**: 2026-02-10
**Scope**: Template provenance lifecycle tracking, version determinism, refresh mechanism
**Status**: PASS (no blocking findings)

---

## Executive Summary

The template provenance system correctly tracks template version metadata through all four DPP lifecycle operations (CREATE, UPDATE, PUBLISH, REBUILD). The `template_provenance` JSONB column on `dpp_revisions` provides a complete audit trail linking each DPP revision to the exact template versions used to build it.

**25 inspection tests written and passing** covering all lifecycle paths, null-safety guards, version determinism, migration structure, and refresh mechanism.

---

## Inspection Scope

| Area | Files Examined |
|------|---------------|
| DPP lifecycle service | `backend/app/modules/dpps/service.py` |
| Database model | `backend/app/db/models.py` (DPPRevision.template_provenance) |
| Migration | `backend/app/db/migrations/versions/0023_template_provenance.py` |
| Template service | `backend/app/modules/templates/service.py` |
| Template catalog | `backend/app/modules/templates/catalog.py` |
| Template router | `backend/app/modules/templates/router.py` |
| Existing tests | `backend/tests/unit/test_dpp_provenance_paths.py` |
| DPP router | `backend/app/modules/dpps/router.py` (RevisionResponse) |

---

## Findings

### F-01: Provenance Correctly Captured at CREATE (PASS)

**Path**: `DPPService.create_dpp()` → `_build_template_provenance()`

The `_build_template_provenance()` method (service.py:889-913) builds provenance from two sources:
1. **Catalog descriptors** (`get_template_descriptor(key)`) — provides `idta_version` and `semantic_id`
2. **DB Template records** — provides `resolved_version`, `source_file_sha`, `source_file_path`, `source_kind`, `selection_strategy`

This dual-source approach ensures provenance includes both the catalog baseline and the actual fetched source metadata.

**Import path** (`create_dpp_from_environment()`) correctly sets `template_provenance={}` since imported environments have no template context.

### F-02: Provenance Preserved Through UPDATE (PASS)

**Path**: `DPPService.update_submodel()` line 644

```python
template_provenance=current_revision.template_provenance or {},
```

The `or {}` guard correctly handles:
- **Existing provenance**: carried forward unchanged
- **None provenance** (legacy revisions): defaults to `{}`

No mutation of the previous revision's provenance dict occurs since the DPPRevision constructor receives the reference directly. This is safe because revisions are immutable DB rows.

### F-03: Provenance Handled Correctly at PUBLISH (PASS)

Two publish paths exist:

| Path | Behavior | Provenance |
|------|----------|------------|
| Draft → Published (in-place flip) | `revision.state = PUBLISHED` | Unchanged on same object |
| Already published (re-publish) | New DPPRevision created | `latest_revision.template_provenance or {}` |

Both paths correctly preserve provenance. The `or {}` guard on the re-publish path (line 759) prevents None leakage.

### F-04: Rebuild Computes FRESH Provenance (PASS)

**Path**: `_rebuild_dpp_from_templates()` → `_build_provenance_from_db_templates()`

This was a **critical fix in PR #48** (BUG-2). The rebuild path now computes fresh provenance from the current DB Template objects rather than copying stale provenance from the old revision. This ensures that after a template refresh + rebuild, the provenance reflects the new template version.

### F-05: Version Determinism via Cache Key (PASS)

The definition cache key is `(template_key, version, source_file_sha)`:

```python
_definition_cache: dict[tuple[str, str, str | None], dict[str, Any]]
```

This means:
- **Same SHA** → cache hit → same definition (deterministic)
- **Different SHA** (e.g., after upstream update) → cache miss → fresh definition built
- **None SHA** (edge case) → cached separately, but unlikely in practice

The `refresh_template()` method correctly invalidates the cache entry on refresh (service.py:328).

### F-06: Provenance JSONB Field Completeness (PASS)

Each provenance entry contains 7 metadata fields:

| Field | Source | Purpose |
|-------|--------|---------|
| `idta_version` | Catalog descriptor | IDTA specification version (e.g., "3.0") |
| `semantic_id` | Catalog descriptor | Full IRI of the template |
| `resolved_version` | DB Template | Resolved upstream version (e.g., "3.0.1") |
| `source_file_sha` | GitHub API | Git blob SHA for content-addressing |
| `source_file_path` | GitHub API | Repository path of the fetched file |
| `source_kind` | Service logic | "json" or "aasx" |
| `selection_strategy` | Service logic | "deterministic_v2" or "fallback_url" |

### F-07: Migration 0023 Structure (PASS)

- Revision ID: `0023_template_provenance` (25 chars, within Alembic's varchar(32) limit)
- Column: `template_provenance JSONB NULLABLE` — correct for backward compatibility
- The previous revision ID was 37 chars and crashed Docker (fixed in PR #46)

### F-08: Template Refresh Mechanism (PASS)

The `POST /templates/refresh` endpoint (router.py:275-316):
- Returns counter summary: `attempted_count`, `successful_count`, `failed_count`, `skipped_count`
- Templates with `refresh_enabled=False` (e.g., battery-passport) are correctly skipped
- Each `TemplateRefreshResult` carries `source_metadata` for provenance auditing

### F-09: RevisionResponse Serialization (PASS)

The DPP router correctly exposes `template_provenance` in the `RevisionResponse` schema (router.py:130) and serializes it in both `get_dpp()` (line 726) and `list_revisions()` (line 1007).

---

## Observations (Non-Blocking)

### OBS-01: Shared Dict Reference in UPDATE Path

In the UPDATE path, `current_revision.template_provenance or {}` with a truthy dict returns the **same object reference** (not a deep copy). This is acceptable because:
1. DPP revisions are immutable DB rows — the previous revision is never modified
2. The provenance dict is never mutated after creation

However, if future code ever mutates provenance in-place, this would be a bug. A defensive `dict(current_revision.template_provenance)` shallow copy would prevent this.

**Severity**: Informational — no action needed with current code.

### OBS-02: No `fetched_at` in Provenance JSONB

The provenance entry does not include the template's `fetched_at` timestamp. While the `source_file_sha` provides content-addressing (same SHA = same content regardless of fetch time), a timestamp could be useful for debugging "when was this template version fetched?"

The `fetched_at` is available on the Template DB record and could be added to provenance if needed for compliance audits.

**Severity**: Informational — the SHA-based approach is sufficient for version determinism.

---

## Test Coverage Summary

| Test Class | Tests | Coverage Area |
|-----------|-------|--------------|
| `TestCreateProvenance` | 4 | CREATE path: provenance capture, import path, field completeness, missing DB template |
| `TestUpdateProvenance` | 3 | UPDATE path: preservation, None default, no mutation |
| `TestPublishProvenance` | 3 | PUBLISH path: draft flip, re-publish, None default |
| `TestRebuildProvenance` | 3 | REBUILD path: fresh computation, no-change skip, field completeness |
| `TestTemplateRefresh` | 3 | Refresh mechanism: counters, source metadata, skip logic |
| `TestVersionDeterminism` | 5 | Cache key structure, hit/miss, strategy constant, semantic IDs |
| `TestProvenanceNullSafety` | 2 | `or {}` regression guards for update and publish |
| `TestMigration0023` | 2 | Revision ID length, column type |
| **Total** | **25** | |

---

## Conclusion

The template provenance system is **well-designed and correctly implemented**. All four lifecycle paths (CREATE, UPDATE, PUBLISH, REBUILD) handle provenance correctly with appropriate null-safety guards. The PR #48 fix for rebuild provenance (computing fresh rather than copying stale) was a critical improvement that is now validated by tests.

No blocking issues found. The two observations are informational only.
