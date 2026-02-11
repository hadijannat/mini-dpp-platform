# Carbon Footprint Remediation Backlog (2026-02-11)

## Implementation Summary
This backlog consolidates the inspection results into implementation-team tickets with dependencies and acceptance criteria.

## Sprint Allocation
- Sprint CF-S1: Completed in this implementation pass (`CF-001`..`CF-009`)
- Sprint CF-S2: Residual hardening and CI gating

## CF-S1 Completed Tickets

### CF-001 — Restore Inspection Bootstrap Script
- Priority: `P1`
- Owner: `EX1` (Template & Versioning)
- Status: `Done`
- Files:
  - `/Users/aeroshariati/mini-dpp-platform/backend/tests/tools/inspection_setup.py`
- Acceptance:
  1. Script initializes DB/session and uses `TemplateRegistryService` directly.
  2. Writes `definition.json`, `schema.json`, `source_metadata.json`, and run summary.

### CF-002 — Restore Referenced Inspection Tests
- Priority: `P1`
- Owner: `EX8` (QA)
- Status: `Done`
- Files:
  - `/Users/aeroshariati/mini-dpp-platform/backend/tests/inspection/test_aasx_roundtrip.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/tests/inspection/test_qualifier_enforcement.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/tests/inspection/test_security_isolation.py`
- Acceptance:
  1. All referenced inspection modules exist and pass.

### CF-003 — Align Frontend UISchema Type Contract
- Priority: `P2`
- Owner: `EX4` (Frontend Forms)
- Status: `Done`
- Files:
  - `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/types/uiSchema.ts`
- Acceptance:
  1. Declares backend-emitted extension keys used by Carbon Footprint forms.

### CF-004 — Enforce Dynamic idShort Constraints
- Priority: `P1`
- Owner: `EX4` (Frontend Forms)
- Status: `Done`
- Files:
  - `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/utils/validation.ts`
  - `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/utils/validation.test.ts`
- Acceptance:
  1. Enforces `x-edit-id-short`, `x-allowed-id-short`, `x-naming` for dynamic keys.
  2. Failure messages are deterministic and test-covered.

### CF-005 — Add Order-Relevant List Reordering
- Priority: `P2`
- Owner: `EX4` (Frontend Forms)
- Status: `Done`
- Files:
  - `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/components/fields/ListField.tsx`
  - `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/types/definition.ts`
  - `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/components/AASRenderer.test.tsx`
- Acceptance:
  1. Lists with `orderRelevant=true` expose move up/down controls.

### CF-006 — Add Frontend LCA API Wrappers
- Priority: `P2`
- Owner: `EX8` (QA/Release)
- Status: `Done`
- Files:
  - `/Users/aeroshariati/mini-dpp-platform/frontend/src/lib/api.ts`
  - `/Users/aeroshariati/mini-dpp-platform/frontend/src/lib/api.test.ts`
- Acceptance:
  1. Typed wrappers exist for calculate/report/compare endpoints.

### CF-007 — Govern PCF Engine Methodology and Multipliers
- Priority: `P1`
- Owner: `EX5` (PCF Domain)
- Status: `Done`
- Files:
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/core/config.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/lca/engine.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/lca/service.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/lca/schemas.py`
- Acceptance:
  1. Engine uses config-provided scope multipliers.
  2. Methodology disclosure propagates to report payload.

### CF-008 — Improve Carbon Footprint Extraction Fidelity
- Priority: `P1`
- Owner: `EX5` (PCF Domain)
- Status: `Done`
- Files:
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/lca/extractor.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/tests/unit/test_lca_extractor.py`
- Acceptance:
  1. Extractor supports CF list paths and material-to-PCF mapping.
  2. Extracts `ExternalPcfApi` references for downstream handling.

### CF-009 — Controlled ExternalPcfApi Resolution
- Priority: `P1`
- Owner: `EX5` (PCF Domain)
- Status: `Done`
- Files:
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/core/config.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/lca/service.py`
  - `/Users/aeroshariati/mini-dpp-platform/backend/tests/unit/test_lca_service_external_pcf.py`
- Acceptance:
  1. External fetch path gated by feature flag.
  2. Host allowlist and timeout are enforced.
  3. Fetch outcomes are logged in persisted report provenance.

## CF-S2 Planned Hardening

### CF-010 — Carbon Footprint CI Gate Job
- Priority: `P1`
- Owner: `EX8`
- Depends on: `CF-001`..`CF-009`
- Scope:
  - Add dedicated workflow target for Carbon Footprint pipeline assertions.

### CF-011 — Dynamic idShort Authoring UX
- Priority: `P2`
- Owner: `EX4`
- Depends on: `CF-004`
- Scope:
  - Add explicit UI for dynamic entry key creation aligned with `x-allowed-id-short` and `x-naming`.

### CF-012 — ExternalPcfApi Contract Adapters
- Priority: `P2`
- Owner: `EX5`
- Depends on: `CF-009`
- Scope:
  - Add partner-specific response adapters and stricter schema validation.

## Regression Gates
- Backend:
  ```bash
  uv run pytest tests/unit/test_template_service.py tests/unit/test_schema_from_definition.py tests/unit/test_basyx_parser.py tests/unit/test_export_service.py tests/unit/test_lca_extractor.py tests/unit/test_lca_service_external_pcf.py tests/inspection/test_aasx_roundtrip.py tests/inspection/test_qualifier_enforcement.py tests/inspection/test_security_isolation.py tests/inspection/test_provenance_lifecycle.py -q
  ```
- Frontend:
  ```bash
  npm test -- --run src/lib/api.test.ts src/features/editor/utils/validation.test.ts src/features/editor/components/AASRenderer.test.tsx src/features/editor/utils/zodSchemaBuilder.test.ts
  ```
