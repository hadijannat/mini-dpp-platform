# Carbon Footprint Findings Register (2026-02-11)

## Legend
- Severity: `P0` data loss/compliance blocker, `P1` functional mismatch, `P2` quality/UX, `P3` optional enhancement
- Status: `Open`, `In Progress`, `Done`, `Deferred`

| ID | Severity | Status | Area | Owner Role | Finding | Evidence Command | Acceptance Test |
|---|---|---|---|---|---|---|---|
| CF-001 | P1 | Done | Inspection Tooling | EX1 | `tests/tools/inspection_setup.py` referenced missing APIs (`get_template_service`, `get_contract`) and was non-executable. | `uv run python tests/tools/inspection_setup.py` | Script ingests templates and writes `ingestion_summary.json` without API lookup errors. |
| CF-002 | P1 | Done | Inspection Harness | EX8 | Inspection package referenced missing test modules in `backend/tests/inspection/__init__.py`. | `uv run pytest tests/inspection/test_aasx_roundtrip.py tests/inspection/test_qualifier_enforcement.py tests/inspection/test_security_isolation.py -q` | Referenced files exist and pass. |
| CF-003 | P2 | Done | Frontend Schema Contract | EX4 | Frontend `UISchema` type omitted backend SMT extensions, causing contract drift and weak compile-time guardrails. | `npm test -- --run src/features/editor/utils/validation.test.ts` | `UISchema` includes emitted `x-*` keys and tests pass. |
| CF-004 | P1 | Done | Frontend Validation | EX4 | `x-allowed-id-short`, `x-edit-id-short`, `x-naming` were emitted but not enforced in save validation. | `npm test -- --run src/features/editor/utils/validation.test.ts` | Invalid dynamic keys are rejected with deterministic errors. |
| CF-005 | P2 | Done | Frontend List UX | EX4 | `orderRelevant` from template definition was not reflected in list UI behavior. | `npm test -- --run src/features/editor/components/AASRenderer.test.tsx` | Lists with `orderRelevant=true` expose move controls; tests pass. |
| CF-006 | P2 | Done | Frontend API Layer | EX8 | LCA endpoints existed in OpenAPI but had no typed client wrappers in frontend API library. | `npm test -- --run src/lib/api.test.ts` | `calculatePcf`, `getLatestPcfReport`, `comparePcfRevisions` wrappers exist and tests pass. |
| CF-007 | P1 | Done | PCF Engine Governance | EX5 | Scope multipliers/methodology were hardcoded placeholders, not runtime-governed or claim-aware. | `uv run pytest tests/unit/test_lca_service_external_pcf.py -q` | Config-driven methodology/multipliers/disclosure are used in service output. |
| CF-008 | P1 | Done | Carbon Footprint Extraction | EX5 | PCF extraction relied on broad heuristics and missed template-path-aware Carbon Footprint structures. | `uv run pytest tests/unit/test_lca_extractor.py -q` | Extractor resolves CF list entries and maps material-to-PCF where available. |
| CF-009 | P1 | Done | ExternalPcfApi Integration | EX5 | No controlled external PCF retrieval/provenance flow despite template support (`ExternalPcfApi`). | `uv run pytest tests/unit/test_lca_service_external_pcf.py -q` | External API references are captured; calls are gated by config allowlist and timeout; fetch log persisted. |

## Run Evidence Snapshot

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

## Residual Open Items
- `P2`: Add dedicated dynamic idShort authoring UX (today: enforced in validation, not interactive authoring widgets).
- `P2`: Extend partner-specific `ExternalPcfApi` payload contract adapters and deterministic signature verification.
- `P2`: Add CI workflow job dedicated to Carbon Footprint full E2E path (refresh -> edit -> LCA -> publish -> export -> re-import).
