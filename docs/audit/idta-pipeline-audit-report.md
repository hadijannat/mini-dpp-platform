# IDTA Template Pipeline Audit Report

**Date:** 2026-02-09
**Scope:** 7-stage pipeline — IDTA GitHub Fetch → BaSyx Parse → Definition AST → JSON Schema → Frontend Forms → BaSyx Instantiation → Export (AASX/JSON/JSON-LD/Turtle)
**Method:** 6 parallel read-only inspection agents, lead synthesis
**Audit Team:** Agents A–F (SMT/Source, Parser/Schema, Frontend, Export, Persistence/Security, QA)

---

## Executive Summary

| Severity | Count | Category Breakdown |
|----------|-------|--------------------|
| **CRITICAL** | 2 | BaSyx lenient mode data loss (D-1, D-10), ESPR tier bypass (E-8) |
| **HIGH** | 4 | Template version not persisted (E-1/E-9), ESPR semantic ID default (E-2), frontend editor tests missing (F-3/C-9), parse stage zero tests (F-1) |
| **MEDIUM** | 7 | XML export not in UI (D-6), AASX content validation (D-8), Zod schema permissive (C-4), SmtQualifiers alignment (C-2), webhook RLS (E-7), conformance test gaps (D-7/D-9), source SHA not validated (A-3) |
| **LOW** | 6 | Blob always readonly (B-8), cache eviction (A-6), semantic registry cache (A-7), deprecated templates (A-10), hash chain break (E-4), Turtle fidelity (D-4) |
| **NO ISSUE** | 17 | SMT qualifiers complete, file selection deterministic, version resolution sound, qualifier parsing correct, element types covered, EntityType complete, value coercion robust, sort deterministic, EPCIS injection safe, OPC relationships OK, encryption safe, public router gated, compliance gate enforced, templates correctly global, formDefaults correct, EitherOr correct, CI gate configured |

**All 10 pre-identified gaps confirmed** with file:line evidence. **5 new findings** discovered.

---

## Findings by Pipeline Stage

### Stage 1: IDTA GitHub Fetch

| ID | Finding | Severity | Evidence | Agent |
|----|---------|----------|----------|-------|
| A-3 | `source_file_sha` stored but never validated on re-fetch — upstream in-place edits undetected | MEDIUM | `templates/service.py:194,328` | A |
| A-4 | Battery passport template correctly marked unavailable — upstream IDTA 02035 not published | INFO | `catalog.py:129-140`, `idta_semantic_registry.json:39-44` | A |
| A-10 | No distinction between network failure and upstream 404 when template removed | LOW | `service.py:415-450` | A |
| F-6 | `compute_golden_hashes.py` requires network access — cannot run in sandboxed environments | LOW | `tests/tools/compute_golden_hashes.py:76-123` | F |

**Pre-identified gaps confirmed:** #4 (battery passport golden missing), #10 (SHA not validated)

### Stage 2: BaSyx Parse

| ID | Finding | Severity | Evidence | Agent |
|----|---------|----------|----------|-------|
| **D-1** | **BaSyx lenient mode is default everywhere** — `basyx_parser.py`, `basyx_builder.py`, `export/service.py` all use `failsafe=True` (implicit). Strict mode only in conformance tests. Malformed template elements silently dropped. | **CRITICAL** | `basyx_parser.py:61-66`, `basyx_builder.py:234`, `export/service.py:136,174` | D |
| **F-1** | **Zero unit tests for `BasyxTemplateParser`** — no tests for corrupt AASX, invalid JSON, malformed BaSyx structure, or parse failure paths | **HIGH** | `backend/tests/unit/` (grep: 0 results for BasyxTemplateParser) | F |

### Stage 3: Definition AST

| ID | Finding | Severity | Evidence | Agent |
|----|---------|----------|----------|-------|
| A-1 | All 16 SMT qualifier semantic IDs correctly match IDTA SMT/Qualifier/1/0 spec | NO ISSUE | `qualifiers.py:16-81` | A |
| A-2 | File selection is fully deterministic — 4-tuple scoring with lexicographic tiebreaker | NO ISSUE | `service.py:670-709` | A |
| B-1 | All 13 AAS element types handled in `_element_definition()` | NO ISSUE | `definition.py:108-163` | B |
| B-2 | `_list_item_definition()` correctly falls back to `typeValueListElement` | NO ISSUE | `definition.py:167-177` | B |
| B-3 | `_sorted_elements()` 3-tuple sort key is deterministic | NO ISSUE | `definition.py:266-272` | B |
| B-10 | Entity.statements and ARE.annotations correctly recurse — 5-level nesting tested | NO ISSUE | `definition.py:130-148`, `test_schema_from_definition.py:788-810` | B |

### Stage 4: JSON Schema Generation

| ID | Finding | Severity | Evidence | Agent |
|----|---------|----------|----------|-------|
| B-4 | All 16 qualifier-to-schema mappings complete in `_apply_smt()` | NO ISSUE | `schema_from_definition.py:284-353` | B |
| B-5 | `VALUE_TYPE_TO_JSON` maps 12 XSD types; `enum_to_str()` returns Python type names not XSD names — unknown types default to "string" | MEDIUM | `schema_from_definition.py:8-21`, `aas/model_utils.py` | B |
| B-7 | `_coerce_value()` handles all edge cases (None, empty, non-ASCII, boolean strings) | NO ISSUE | `schema_from_definition.py:399-420` | B |
| B-8 | `_blob_schema()` hardcodes `x-readonly: True` — may prevent user blob uploads in edge cases | LOW | `schema_from_definition.py:189-200` | B |
| B-9 | `_entity_schema()` EntityType enum complete (SelfManagedEntity, CoManagedEntity) | NO ISSUE | `schema_from_definition.py:223-247` | B |

### Stage 5: Frontend Forms

| ID | Finding | Severity | Evidence | Agent |
|----|---------|----------|----------|-------|
| **C-1** | **RelationshipField renders first/second as raw JSON text** — `JSON.stringify()` display + manual JSON input with no parse error feedback | **MEDIUM** | `RelationshipField.tsx:22-48` | C |
| **C-2** | **Frontend `SmtQualifiers` type missing 6 fields** vs backend: `default_value`, `initial_value`, `example_value`, `naming`, `allowed_id_short`, `edit_id_short` | **MEDIUM** | `definition.ts:3-14` vs `qualifiers.py:92-108` | C |
| C-3 | AASRenderer covers all 13 element types — correct dispatch | NO ISSUE | `AASRenderer.tsx:51-106` | C |
| **C-4** | **Zod RelationshipElement schema uses `z.unknown().nullable()`** for first/second — accepts any value, no Reference structure validation | **MEDIUM** | `zodSchemaBuilder.ts:56-57` | C |
| C-5 | `useEitherOrGroups` correctly implements "at least one" semantics per IDTA spec | NO ISSUE | `useEitherOrGroups.ts:14-57` | C |
| C-6 | `formDefaults.ts` Entity initialization correct (SelfManagedEntity default) | NO ISSUE | `formDefaults.ts:11-13` | C |
| C-7 | PropertyField enforces form_choices, allowed_value_regex, allowed_range via Zod — but no HTML min/max hints | LOW | `PropertyField.tsx:39-103`, `zodSchemaBuilder.ts:68-110` | C |
| C-8 | ReadOnlyField vs AccessMode distinction consistent | NO ISSUE | `AASRenderer.tsx:34-48` | C |
| **C-9** | **Only 7 test files for 13+ editor components** — zero component-level tests for RelationshipField, EntityField, ListField, etc. | **HIGH** | `frontend/src/features/editor/` (7 test files) | C |

### Stage 6: BaSyx Instantiation

| ID | Finding | Severity | Evidence | Agent |
|----|---------|----------|----------|-------|
| **D-10** | **DPP update path uses lenient BaSyx deserialization** — user edits introducing schema violations cause silent data loss on next save | **CRITICAL** | `basyx_builder.py:224-245` (no `failsafe=False`) | D |
| **E-1** | **DPPRevision model lacks template_version, template_key, and schema_hash columns** — impossible to trace which template version produced a DPP revision | **HIGH** | `models.py:433-495` | E |
| E-9 | **`create_dpp()` does not store contract hash or template version** — `selected_templates` list passed but not persisted | **HIGH** | `dpps/service.py:75-163` | E |

### Stage 7: Export

| ID | Finding | Severity | Evidence | Agent |
|----|---------|----------|----------|-------|
| D-2 | AASX OPC relationships handled correctly by BaSyx `pyecma376_2` | NO ISSUE | `export/service.py:183-198` | D |
| D-3 | JSON-LD uses custom `@context` (WoT TD + admin-shell.io namespace) — no official IDTA JSON-LD context exists | MEDIUM | `aas/serialization.py:26-27,90-97` | D |
| D-4 | Turtle round-trip test compares triple count only, not content isomorphism | LOW | `test_rdf_export.py:90-101` | D |
| D-5 | EPCIS traceability submodel injection is in-memory only — safe, not persisted | NO ISSUE | `export/service.py:42-71` | D |
| **D-6** | **XML export exists in backend but missing from frontend dropdown** — 5 formats exposed, 6 supported | **MEDIUM** | `export/service.py:122-145` vs frontend export menu | D |
| **D-7** | **Only 4 conformance tests** — missing AASX file validation via `aas-test-engines`, no template-generated DPP tests | **MEDIUM** | `tests/conformance/test_aas_conformance.py` (4 methods) | D |
| **D-8** | **AASX structural validator checks presence/parseability only** — no content type, relationship target, or IDTA Part 5 naming validation | **MEDIUM** | `export/service.py:247-302` | D |
| D-9 | `aas-test-engines` gated by `skip_no_engines` — but always installed in CI (no real skip) | MEDIUM | `test_aas_conformance.py:23` | D |

---

## Cross-Cutting Concerns

### Data Integrity

| ID | Finding | Severity | Evidence | Agent |
|----|---------|----------|----------|-------|
| **E-1/E-9** | **Template version provenance gap** — DPPRevision stores `aas_env_json` and `digest_sha256` but no reference to which template version/schema was used at creation time. If `definition.py` or `schema_from_definition.py` changes, past revisions can't be reconstructed. | **HIGH** | `models.py:433-495`, `dpps/service.py:75-163` | E |
| A-3/A-10 | **Source file integrity** — `source_file_sha` stored but never checked; upstream removal indistinguishable from network error | MEDIUM + LOW | `templates/service.py:194,328,415-450` | A |
| E-4 | **Hash chain verification stops at first mismatch** — incomplete forensics if multiple events tampered | LOW | `crypto/verification.py:100-140` | E |
| A-6 | **Definition cache unbounded TTL** — FIFO eviction (max 32 entries) but no time-based expiry | LOW | `service.py:38-42,394-398` | A |
| A-7 | **Semantic registry `lru_cache` never invalidated** — changes require process restart | LOW | `semantic_registry.py:19-25` | A |

### Security & Access Control

| ID | Finding | Severity | Evidence | Agent |
|----|---------|----------|----------|-------|
| **E-8** | **ESPR tier=None returns full unfiltered environment** — unauthenticated users can access ALL submodels by omitting `?espr_tier=` query param | **CRITICAL** | `submodel_filter.py:29-46`, `public_router.py:275,293` | E |
| **E-2** | **Submodels without semantic ID visible to ALL tiers** — `_submodel_matches_tier()` returns `True` for missing semantic IDs (deny-by-default violation) | **HIGH** | `submodel_filter.py:64-72` | E |
| E-7 | **`webhook_delivery_log` lacks RLS** — no `tenant_id` column, joins via FK to `webhook_subscriptions` only | MEDIUM | `models.py:1431-1482` | E |
| E-3 | Templates correctly global (no `tenant_id`) — intentional design | NO ISSUE | `models.py:558-628` | E |
| E-5 | Encryption: no plaintext logging, `key_id` column supports future rotation | NO ISSUE | `encryption.py:1-114` | E |
| E-6 | Public router correctly gates on `DPP.status == DPPStatus.PUBLISHED` | NO ISSUE | `public_router.py:98-109` | E |
| E-10 | Compliance pre-publish gate correctly blocks with `ValueError` on violations | NO ISSUE | `dpps/service.py:718-726` | E |

### Test Coverage

| ID | Finding | Severity | Evidence | Agent |
|----|---------|----------|----------|-------|
| **F-1** | **Parse stage: zero tests** for `BasyxTemplateParser` — no corrupt AASX, malformed JSON, or error path coverage | **HIGH** | `backend/tests/unit/` — no matching files | F |
| **C-9/F-3** | **Frontend editor: 7 unit test files** for 13+ components; zero Playwright E2E for form submission workflow | **HIGH** | `frontend/src/features/editor/` | C, F |
| F-2 | Golden file test stops at first hash failure — must compute all locally | MEDIUM | `test_template_goldens.py:44-93` | F |
| F-4 | Conformance tests always run in CI (not conditionally skipped) — correct | NO ISSUE | `.github/workflows/ci.yml:290` | F |
| F-5 | `audit_template_rendering.py` covers all 7 templates with 14 renderer mappings | NO ISSUE | `tests/tools/audit_template_rendering.py` | F |
| F-7 | CI gate correctly configured — conformance failure blocks merge | NO ISSUE | `.github/workflows/ci.yml` | F |
| F-8 | Only 1 file with negative tests (`test_encryption.py`) — zero for templates | HIGH | `backend/tests/` grep results | F |

---

## Known Gaps Status Table

| Gap # | Description | Status | Evidence | Severity | Dependency |
|-------|-------------|--------|----------|----------|------------|
| **#1** | DPP revisions don't store template version references | **CONFIRMED** | `models.py:433-495` — no `template_version`, `template_key`, or `schema_hash` columns | HIGH | Blocks #9 fix |
| **#2** | Templates are global (not tenant-scoped) | **CONFIRMED — BY DESIGN** | `models.py:558-628` — no `tenant_id`; templates are IDTA-sourced platform resources | N/A | — |
| **#3** | ESPR tier filtering permissive default for elements without semantic ID | **CONFIRMED** | `submodel_filter.py:71` — `return True` for missing semantic IDs | HIGH | Independent |
| **#4** | Battery passport golden file missing | **CONFIRMED — BLOCKED UPSTREAM** | `catalog.py:129-140` — IDTA 02035 not published in `admin-shell-io/submodel-templates` | INFO | External |
| **#5** | No frontend editor E2E tests | **CONFIRMED** | 7 unit test files only; `navigation.spec.ts` covers nav, not form submission | HIGH | Independent |
| **#6** | RelationshipElement rendered as JSON text, not structured form | **CONFIRMED** | `RelationshipField.tsx:22-48` — `JSON.stringify()` + raw JSON input | MEDIUM | Depends on C-4 |
| **#7** | Round-trip AASX validation lenient — BaSyx skips malformed objects | **CONFIRMED** | `basyx_parser.py:61-66`, `basyx_builder.py:234`, `export/service.py:136,174` | CRITICAL | Core of D-1 |
| **#8** | Audit hash chain failures: stops at first mismatch (not silent skip) | **RECLASSIFIED** | `crypto/verification.py:136` — `break` after first mismatch; error IS recorded | LOW | Independent |
| **#9** | Schema hash not stored at DPP creation time | **CONFIRMED** | `dpps/service.py:75-163` — `selected_templates` list not persisted | HIGH | Depends on #1 |
| **#10** | Template source SHA stored but not validated on fetch | **CONFIRMED** | `service.py:194,328` — SHA in DB, only used for cache invalidation | MEDIUM | Independent |

### New Findings (Not Pre-Identified)

| ID | Description | Severity | Evidence |
|----|-------------|----------|----------|
| E-7 | `webhook_delivery_log` lacks RLS — no tenant_id column | MEDIUM | `models.py:1431-1482` |
| D-6 | XML export in backend but missing from frontend dropdown | MEDIUM | `export/service.py:122-145` |
| B-5 | `VALUE_TYPE_TO_JSON` missing 20+ XSD types; `enum_to_str()` returns Python names | MEDIUM | `schema_from_definition.py:8-21` |
| C-2 | Frontend `SmtQualifiers` missing 6 fields vs backend | MEDIUM | `definition.ts:3-14` |
| E-8 | ESPR tier=None returns full environment for unauthenticated users | CRITICAL | `submodel_filter.py:29-46` |

---

## Prioritized Remediation Plan

### P0 — Critical (Security + Data Integrity)

**Epic 1: BaSyx Strict Mode Enforcement**
- Dependency: None (standalone)
- Files: `basyx_parser.py`, `basyx_builder.py`, `export/service.py`
- Tasks:
  1. Set `failsafe=False` in `basyx_parser.py:parse_json()` default path
  2. Add `failsafe=False` to `basyx_builder.py:_load_environment()` line 234
  3. Add `failsafe=False` to `export/service.py` JSON→BaSyx deserialization (lines 136, 174)
  4. Add catch-and-report for `BasyxDeserializationError` with user-facing error messages
  5. Regression test: feed malformed JSON → verify exception (not silent skip)

**Epic 2: ESPR Tier Access Control Hardening**
- Dependency: None (standalone)
- Files: `submodel_filter.py`, `dpps/public_router.py`
- Tasks:
  1. Change `submodel_filter.py:71` from `return True` to `return False` (deny-by-default for missing semantic IDs)
  2. Change `submodel_filter.py:45-46`: when `espr_tier is None` for public routes, default to consumer tier
  3. Add config flag `espr_default_tier_for_anonymous: str = "consumer"` for rollout control
  4. Regression tests: verify unauthenticated access returns consumer-tier-only data

### P1 — High (Data Provenance + Test Coverage)

**Epic 3: Template Version Provenance**
- Dependency: Must fix before any compliance audit requiring traceability
- Files: `models.py`, new migration `0023_`, `dpps/service.py`
- Tasks:
  1. Add `template_metadata: Mapped[dict | None] = mapped_column(JSONB)` to `DPPRevision`
  2. Migration `0023_dpp_revision_template_metadata.py` — add nullable JSONB column
  3. In `create_dpp()`, capture and persist `{template_key, idta_version, resolved_version, semantic_id, contract_hash}`
  4. In `update_dpp()`, carry forward template metadata from previous revision
  5. Expose template metadata in revision history API response

**Epic 4: Frontend Editor Test Infrastructure**
- Dependency: None (standalone)
- Files: `frontend/src/features/editor/**/*.test.*`, `frontend/tests/e2e/`
- Tasks:
  1. Add component tests for all 13 field types (RelationshipField, EntityField, ListField highest priority)
  2. Add Playwright E2E: create DPP → open editor → fill form → submit → verify saved
  3. Add Playwright E2E: validation error display for required fields

**Epic 5: Template Parse Negative Tests**
- Dependency: Epic 1 (strict mode must be enabled first)
- Files: `backend/tests/unit/test_basyx_parser.py` (new)
- Tasks:
  1. Test corrupt AASX (invalid ZIP)
  2. Test malformed JSON (missing `modelType`, invalid `assetKind`)
  3. Test network failure during `refresh_template()`
  4. Test GitHub API 404 vs timeout distinction

### P2 — Medium (Compliance + UX)

**Epic 6: Export Completeness**
- Tasks:
  1. Add XML format to frontend export dropdown
  2. Add `aas-test-engines` AASX file validation to conformance test suite
  3. Improve Turtle round-trip test to use `Graph.isomorphic()` instead of triple count

**Epic 7: Frontend Schema Alignment**
- Tasks:
  1. Add 6 missing fields to frontend `SmtQualifiers` type
  2. Replace `z.unknown().nullable()` with structured Reference schema in zodSchemaBuilder
  3. Replace raw JSON input in RelationshipField with structured reference builder

**Epic 8: Source Integrity**
- Tasks:
  1. Validate `source_file_sha` on re-fetch — warn on drift
  2. Distinguish HTTP 404 from network failure in template refresh
  3. Add `webhook_delivery_log` tenant_id + RLS migration

### P3 — Low (Operational)

- Add TTL to `_definition_cache` (24h expiry)
- Document `semantic_registry.py` cache requires restart for changes
- Continue hash chain verification past first mismatch
- Check Blob `access_mode` before hardcoding `x-readonly`
- Add `deprecated_at` column to Template model

---

## Alignment Matrix

| DPP4.0 Requirement | Pipeline Stage | Status | Gap ID |
|---------------------|---------------|--------|--------|
| Template semantic fidelity | Definition AST | PASS — 16/16 qualifiers, 13/13 element types | — |
| Deterministic template selection | Fetch | PASS — deterministic_v2 scoring | — |
| Template version traceability | Instantiation | **FAIL** — no version persisted | E-1, E-9 |
| AAS metamodel conformance | Export | PARTIAL — JSON/XML validated, AASX not | D-7, D-8 |
| ESPR tiered access | Frontend + Backend | **FAIL** — permissive defaults | E-2, E-8 |
| IDTA Part 5 AASX structure | Export | PARTIAL — basic structure OK, no deep validation | D-8 |
| Audit trail integrity | Persistence | PARTIAL — hash chain stops at first break | E-4 |
| Data integrity on edit | Instantiation | **FAIL** — lenient BaSyx drops data silently | D-1, D-10 |
| RDF interoperability | Export | PARTIAL — custom vocabulary, triple-count test only | D-3, D-4 |
| Source provenance | Fetch | PARTIAL — SHA stored, not validated | A-3 |

---

## Appendix: Files Examined

### Backend
- `app/modules/templates/catalog.py`, `qualifiers.py`, `definition.py`, `schema_from_definition.py`, `service.py`, `basyx_parser.py`
- `app/modules/dpps/basyx_builder.py`, `service.py`, `submodel_filter.py`, `public_router.py`, `repository.py`
- `app/modules/export/service.py`
- `app/modules/aas/serialization.py`, `conformance.py`, `model_utils.py`, `references.py`
- `app/core/crypto/verification.py`, `encryption.py`, `config.py`
- `app/db/models.py`, `migrations/versions/0005_*.py`, `0008_*.py`, `0009_*.py`, `0022_*.py`
- `tests/unit/test_schema_from_definition.py`, `test_export_service.py`, `test_rdf_export.py`
- `tests/conformance/test_aas_conformance.py`
- `tests/e2e/test_template_goldens.py`
- `tests/tools/audit_template_rendering.py`, `compute_golden_hashes.py`

### Frontend
- `src/features/editor/components/AASRenderer.tsx`
- `src/features/editor/components/fields/RelationshipField.tsx`, `EntityField.tsx`, `PropertyField.tsx`
- `src/features/editor/utils/zodSchemaBuilder.ts`, `formDefaults.ts`
- `src/features/editor/types/definition.ts`
- `src/features/editor/hooks/useEitherOrGroups.ts`, `useSubmodelForm.ts`
- All 7 editor test files

### CI/CD
- `.github/workflows/ci.yml`, `dpp-pipeline.yml`
