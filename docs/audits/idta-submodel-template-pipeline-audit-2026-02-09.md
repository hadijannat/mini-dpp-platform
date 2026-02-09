# IDTA Submodel Template Pipeline Audit (2026-02-09)

## Scope and Baseline
- Baseline: IDTA DPP4.0 + AAS Part 1/2/5 + ESPR-facing public view.
- Audit target: template resolution/fetch, BaSyx parsing, definition/schema contract generation, frontend form rendering, DPP persistence, export conformance, and public viewer behavior.
- Evidence date: 2026-02-09.

## Pipeline Architecture Map

| Stage | Inputs | Processing | Outputs | Implementation |
|---|---|---|---|---|
| 1. Template source/version resolution | Template key, configured major.minor baseline, Git ref | Query GitHub Contents API, discover available patch dirs, deterministic filename selection, fallback raw URL builder | `resolved_version`, source metadata (`repo_ref`, `file_path`, `sha`, kind, selection strategy) | `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/service.py` |
| 2. Template fetch + persistence | Resolved source URLs/files | Download JSON/AASX, normalize to AAS environment JSON, persist template row + source metadata | `templates.template_json`, `templates.template_aasx` (optional), provenance fields | `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/router.py`, `/Users/aeroshariati/mini-dpp-platform/backend/app/db/models.py`, `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/service.py` |
| 3. BaSyx parsing to canonical AST | Stored template JSON/AASX | Parse via BaSyx (`AASXReader`/JSON adapter), pick submodel by semantic ID/kind, build deterministic AST and qualifier semantics | Template definition AST (`definition`) | `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/basyx_parser.py`, `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/definition.py` |
| 4. Contract schema generation | AST definition | Convert AST to deterministic JSON Schema with SMT qualifier-derived extensions | `/{template_key}/contract` response (`definition`, `schema`, source metadata) | `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/schema_from_definition.py`, `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/router.py` |
| 5. Frontend rendering + validation | Template contract + DPP submodel data | Render recursive editor widgets, hydrate values, enforce readonly/required/either-or/range/multilang behavior | Editable form/JSON UI and validated payloads | `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/pages/SubmodelEditorPage.tsx`, `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/components/AASRenderer.tsx`, `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/utils/*.ts` |
| 6. Submodel mutation + persistence | Template key, submodel payload, latest revision | Update or rebuild submodel through BaSyx object model, create immutable draft revision snapshot | New `dpp_revisions.aas_env_json` revision | `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/service.py`, `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/basyx_builder.py` |
| 7. Export + conformance checks | Revision AAS environment | Export JSON/XML/AASX, validate package structure and BaSyx round-trip | Export payload + compliance validation result | `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/export/service.py`, `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/aas/conformance.py` |
| 8. Public viewer delivery | Published DPP ID/slug + tenant slug | Unauthenticated public API fetch + ESPR categorization + tier filtering | Viewer page with public DPP + categorized submodels | `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/public_router.py`, `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/viewer/pages/DPPViewerPage.tsx`, `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/viewer/utils/esprCategories.ts` |

## Alignment Matrix

| Criterion | Evidence | Status |
|---|---|---|
| 1. Deterministic latest patch resolution per supported template | Upstream snapshot confirms latest patch discovery and deterministic filename selection for supported templates; unsupported battery folder returns 404. See `/Users/aeroshariati/mini-dpp-platform/docs/audits/idta-upstream-resolution-evidence-2026-02-09.json`. | **Aligned** (with explicit unsupported handling) |
| 2. Stored templates parse to BaSyx objects without deferred contract failures | Contract generation path is AST-first and covered by unit tests for definition/schema consistency. Refresh now reports per-template status, including skipped unavailable entries. | **Mostly aligned** |
| 3. Form contracts render intended editable fields with SMT semantics | Renderer + validation suites pass (AASRenderer/zod/validation). Full rendering audit reports 97.2% editable coverage across supported templates with explicit gaps tracked in `/Users/aeroshariati/mini-dpp-platform/docs/audits/idta-template-rendering-audit-2026-02-09.json`. | **Mostly aligned** |
| 4. Submodel edits round-trip through BaSyx and persist valid environments | BaSyx builder unit suite passes; DPP service persists immutable revisions on update/rebuild. | **Aligned** (unit-backed) |
| 5. Exported AASX passes structural + BaSyx round-trip checks | Export + conformance test suites pass (`test_export_service`, `test_aas_conformance`). | **Aligned** |
| 6. Public viewer is unauthenticated and semantic categorization/tier logic is correct | Viewer switched to `/api/v1/public/...` endpoints and now has regression tests for ID and slug paths. Tier prefixes now source from shared semantic registry. | **Aligned** |

## Findings (Prioritized)

### Backend Track

1. **P1: Battery template remains unavailable upstream**
- Evidence: `battery-passport` `published/Battery Passport/1/0` returns 404 in upstream snapshot.
- Impact: battery template cannot be refreshed from source.
- Mitigation implemented: catalog support policy now marks it unavailable and refresh-disabled; refresh API reports `skipped` with reason instead of silent partial success.

2. **P2: Refresh response `count` communicates only successful refreshes**
- Evidence: `/templates/refresh` response `count` maps to refreshed template rows, while `refresh_results` includes skipped/failed entries.
- Impact: clients relying on `count` for total attempted templates can misread outcomes.
- Suggested fix: add explicit `attempted_count` and `successful_count` fields, or redefine `count` semantics in API docs.

3. **P2: Semantic policy still has one manual synchronization edge**
- Evidence: shared registry is now consumed by backend/frontend, but OPA policy remains manually updated.
- Impact: possible future drift between app semantic rules and policy enforcement.
- Suggested fix: generate OPA semantic sets from shared registry during build/release.

4. **P2: Some template structures are visible but weakly editable**
- Evidence: rendering audit reports 6 aggregate gaps (`childless collections`, `statement-less entities`, and relationship editing limitations).
- Impact: operators can view structures that are difficult to edit meaningfully.
- Suggested fix: add explicit UI states for empty containers and richer editors for relationship/entity-heavy templates.

### Frontend Track

1. **P1: Public viewer endpoint mismatch (previously tenant-auth path)**
- Impact: anonymous ESPR view could fail despite backend public API support.
- Mitigation implemented: viewer now calls public endpoints for both ID and slug routes; regression tests added.

2. **P2: Category fallback remains heuristic for unknown semantic IDs**
- Evidence: `idShort` pattern fallback remains when semantic ID has no registry match.
- Impact: custom/non-registered submodels may be bucketed imperfectly.
- Suggested fix: add “unclassified” telemetry and admin-level category override map.

3. **P2: Relationship-heavy templates have limited editing UX**
- Evidence: rendering audit flags relationship references in hierarchical structures as minimally rendered.
- Impact: higher risk of incorrect edits in relationship-dense submodels.
- Suggested fix: add dedicated `first/second` reference editors and entity statement helpers.

## Remediation Backlog (Implementation Sequence)

1. **Stabilize refresh contract semantics**
- Change: add `attempted_count`, `successful_count`, `failed_count`, `skipped_count` to refresh response.
- Risk: low.
- Verify: API contract tests + frontend refresh UI expectations.

2. **Policy generation from shared semantic registry**
- Change: derive OPA semantic sets from `/Users/aeroshariati/mini-dpp-platform/shared/idta_semantic_registry.json`.
- Risk: medium (policy rollout and CI integration).
- Verify: OPA unit tests and tier visibility regression tests.

3. **Unsupported template lifecycle policy**
- Change: expose support status in UI and block unavailable templates from selection flows.
- Risk: low.
- Verify: template list UI tests + create/edit flow tests.

4. **Optional: classify unknown semantics explicitly**
- Change: add `unclassified` ESPR bucket with admin warning/logging.
- Risk: low.
- Verify: viewer classification tests with unknown semantic IDs.

5. **Improve relationship/entity editing ergonomics**
- Change: add dedicated relationship reference pickers and statement editors.
- Risk: medium.
- Verify: renderer integration tests + `audit_template_rendering` delta check.

## Verification Executed

- Backend:
  - `uv run pytest tests/unit/test_template_service.py tests/unit/test_battery_template.py tests/unit/test_espr_tiered_access.py -q`
  - `uv run pytest tests/unit/test_public_dpp.py tests/unit/test_public_aas_repository.py tests/unit/test_espr_tiered_access.py -q`
  - `uv run pytest tests/unit/test_export_service.py tests/unit/test_aas_conformance.py tests/unit/test_basyx_builder.py -q`
  - `uv run ruff check app/modules/templates app/modules/dpps tests/unit/test_template_service.py tests/unit/test_battery_template.py`
  - `uv run mypy app/modules/templates app/modules/dpps app/modules/semantic_registry.py`
- Frontend:
  - `npm test -- --run src/features/viewer/pages/__tests__/DPPViewerPage.test.tsx src/features/viewer/utils/__tests__/esprCategories.test.ts src/features/editor/components/AASRenderer.test.tsx src/features/editor/utils/zodSchemaBuilder.test.ts src/features/editor/utils/validation.test.ts`
  - `npm run typecheck`
  - `npm run lint` (existing warnings outside scope in UI primitives)
- Rendering audit:
  - `uv run python tests/tools/audit_template_rendering.py --json`
  - Evidence artifact: `/Users/aeroshariati/mini-dpp-platform/docs/audits/idta-template-rendering-audit-2026-02-09.json`

## Assumptions and Defaults Used
- Upstream source of truth: `admin-shell-io/submodel-templates` on branch `main`.
- Audit date reference: 2026-02-09.
- Environment-dependent full docker e2e flows were not required for this pass; verification is code+unit/integration-test evidence plus live upstream source inspection.
