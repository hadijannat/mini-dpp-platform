# Carbon Footprint Pipeline Map (2026-02-11)

## Scope
Repository-grounded inspection of Carbon Footprint template flow:

1. Template fetch/version resolution
2. BaSyx parse/normalize
3. Definition/schema generation
4. Frontend form rendering/validation
5. DPP submodel persistence + provenance
6. PCF calculation/proposal layer
7. AASX/XML/JSON-LD/Turtle export
8. Public/tier filtering

## Upstream Baseline
- Upstream source: `admin-shell-io/submodel-templates@main`
- Carbon Footprint latest published patch verified: `1.0.1`
- Path: `published/Carbon Footprint/1/0/1`
- Known upstream issues tracked in scope: #195, #124, #130, #135, #159, #224

## Stage Map

### Stage 1: Source Resolution and Fetch
- Backend entrypoints:
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/catalog.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/service.py`
- Key behavior:
  - `latest_patch` resolution inside configured major/minor baseline.
  - Deterministic asset selection from GitHub contents API.
  - Persisted metadata: `resolved_version`, `source_file_path`, `source_file_sha`, `source_kind`, `selection_strategy`.

### Stage 2: BaSyx Parse and Template Contract
- Backend entrypoints:
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/basyx_parser.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/definition.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/schema_from_definition.py`
- Key behavior:
  - AASX/JSON parse to BaSyx object store.
  - Semantic-id targeted submodel selection.
  - Stable definition AST.
  - JSON schema generation with SMT qualifier projection (`x-*` extensions).

### Stage 3: Frontend Contract Consumption
- Frontend entrypoints:
  - `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/pages/SubmodelEditorPage.tsx`
  - `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/components/AASRenderer.tsx`
  - `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/components/fields/ListField.tsx`
  - `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/utils/validation.ts`
- Key behavior:
  - Dynamic field rendering from definition + schema.
  - Zod + save-time validation.
  - Carbon Footprint list handling with add/remove and order controls when `orderRelevant=true`.
  - Dynamic idShort policy validation (`x-allowed-id-short`, `x-edit-id-short`, `x-naming`).

### Stage 4: DPP Update and Persistence
- Backend entrypoints:
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/basyx_builder.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/service.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/db/models.py`
- Key behavior:
  - Submodel updates create new immutable revisions.
  - Provenance carry-forward in `template_provenance`.
  - Digest/signature lifecycle preserved.

### Stage 5: PCF Calculation/Proposal Layer
- Backend entrypoints:
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/lca/extractor.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/lca/engine.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/lca/service.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/lca/router.py`
- Key behavior:
  - Config-governed scope multipliers and methodology disclosure.
  - Template-path-aware Carbon Footprint extraction.
  - Controlled `ExternalPcfApi` resolution with allowlist + timeout + fetch log provenance.

### Stage 6: Export and Conformance
- Backend entrypoints:
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/export/service.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/tests/tools/aasx_roundtrip_validator.py`
- Key behavior:
  - JSON/AASX/XML/JSON-LD/Turtle/PDF export.
  - Structural AASX checks plus BaSyx round-trip validation.

### Stage 7: Public View and Tier Filtering
- Backend entrypoints:
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/public_router.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/submodel_filter.py`
  - `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/viewer/utils/esprCategories.ts`
- Key behavior:
  - Public confidentiality filtering.
  - Tier-based submodel filtering using semantic registry prefixes.
  - Carbon footprint classification to environmental category.

## Validation Executed (This Run)

### Backend
```bash
uv run pytest tests/unit/test_template_service.py tests/unit/test_schema_from_definition.py tests/unit/test_basyx_parser.py tests/unit/test_export_service.py tests/unit/test_lca_extractor.py tests/unit/test_lca_service_external_pcf.py tests/inspection/test_aasx_roundtrip.py tests/inspection/test_qualifier_enforcement.py tests/inspection/test_security_isolation.py tests/inspection/test_provenance_lifecycle.py -q
```
- Result: `130 passed`

### Frontend
```bash
npm test -- --run src/lib/api.test.ts src/features/editor/utils/validation.test.ts src/features/editor/components/AASRenderer.test.tsx src/features/editor/utils/zodSchemaBuilder.test.ts
```
- Result: `68 passed`

## Key Deltas Implemented During This Inspection
- Fixed stale inspection bootstrap script (`tests/tools/inspection_setup.py`).
- Restored missing inspection test modules listed in inspection package docstring.
- Extended frontend UI schema typing for backend-emitted SMT extensions.
- Added dynamic idShort policy checks in frontend validation.
- Added list reordering controls for `orderRelevant` lists.
- Added typed frontend LCA API wrappers (`calculatePcf`, `getLatestPcfReport`, `comparePcfRevisions`).
- Replaced hardcoded PCF engine multipliers with config-governed settings.
- Added methodology disclosure plumbing into LCA outputs.
- Added template-path-aware Carbon Footprint extraction and `ExternalPcfApi` reference capture.
- Added controlled external PCF resolution flow with allowlist/timeouts and provenance logging.

## Residual Risks
- Full UI authoring for dynamic idShort creation workflows is still limited (validation now enforced, but no dedicated dynamic key editor UX).
- `ExternalPcfApi` payload schema is intentionally generic; partner-specific contracts require adapter hardening.
- Upstream IDTA PDF/AASX mismatch remains an external dependency and must stay in regression watchlist.
