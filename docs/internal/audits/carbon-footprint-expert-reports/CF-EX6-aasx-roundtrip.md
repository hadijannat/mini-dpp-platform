# CF-EX6 BaSyx and AASX Compliance

## Owner
BaSyx/AASX Compliance Specialist

## Scope
- `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/export/service.py`
- `/Users/aeroshariati/mini-dpp-platform/backend/tests/unit/test_export_service.py`
- `/Users/aeroshariati/mini-dpp-platform/backend/tests/tools/aasx_roundtrip_validator.py`
- `/Users/aeroshariati/mini-dpp-platform/backend/tests/inspection/test_aasx_roundtrip.py`

## Findings
1. Inspection package referenced AASX round-trip validation but did not include an inspection-level regression module (`CF-002`).
2. Carbon Footprint export path required explicit evidence for format coverage and structural read-back.
3. Supplementary file and structural validation behavior needed deterministic classification checks.

## Implemented
- Added inspection-level AASX roundtrip regression test module.
- Verified export behavior for JSON/AASX/XML flows through existing export service tests and inspection checks.
- Documented evidence commands and acceptance criteria for conformance gate use.

## Evidence Command
```bash
uv run pytest tests/unit/test_export_service.py tests/inspection/test_aasx_roundtrip.py -q
```

## Acceptance Criteria
- Carbon Footprint DPP exports are readable by BaSyx round-trip validator without missing identifiables.
- Structural validation failures are surfaced as explicit warnings/errors, not silent pass-through.
- Export service tests and inspection roundtrip tests both pass in local and CI environments.
