# CF-EX8 QA and Release Gating

## Owner
QA and Release Gating Specialist

## Scope
- `/Users/aeroshariati/mini-dpp-platform/backend/tests/e2e/test_dpp_pipeline.py`
- `/Users/aeroshariati/mini-dpp-platform/frontend/tests/e2e/qualifierEnforcement.spec.ts`
- `/Users/aeroshariati/mini-dpp-platform/.github/workflows/`
- `/Users/aeroshariati/mini-dpp-platform/backend/tests/inspection/`
- `/Users/aeroshariati/mini-dpp-platform/frontend/src/lib/api.ts`

## Findings
1. Inspection package referenced missing inspection modules, breaking intended gate entrypoints (`CF-002`).
2. Frontend lacked typed LCA API wrappers despite available backend endpoints (`CF-006`).
3. Carbon Footprint-specific CI gate remains a planned hardening item (`CF-010` in backlog).

## Implemented
- Added inspection modules used as deterministic backend gate checks.
- Added typed frontend API wrappers for calculate/report/compare LCA endpoints and tests.
- Documented gate command matrix in leader remediation backlog.

## Evidence Command
```bash
uv run pytest tests/inspection/test_aasx_roundtrip.py tests/inspection/test_qualifier_enforcement.py tests/inspection/test_security_isolation.py -q
npm test -- --run src/lib/api.test.ts src/features/editor/components/AASRenderer.test.tsx src/features/editor/utils/validation.test.ts
```

## Acceptance Criteria
- Inspection gate modules execute cleanly in local runs and CI.
- Frontend API layer exposes typed LCA methods used by future E2E gate flows.
- Carbon Footprint release checklist includes backend + frontend gate commands with deterministic pass/fail criteria.
