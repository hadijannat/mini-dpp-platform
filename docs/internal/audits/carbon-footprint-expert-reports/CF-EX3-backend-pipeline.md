# CF-EX3 Backend Parser and Pipeline

## Owner
Backend Parser/Schema/Pipeline Specialist

## Scope
- `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/basyx_parser.py`
- `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/basyx_builder.py`
- `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/service.py`

## Findings
1. Semantic-id targeting and submodel replacement/update flow are stable.
2. List hydration/dehydration is functional for existing element types.
3. Inspection referenced tests for AASX roundtrip were missing (`CF-002`).

## Implemented
- Added inspection roundtrip test: `/Users/aeroshariati/mini-dpp-platform/backend/tests/inspection/test_aasx_roundtrip.py`.

## Evidence Command
```bash
uv run pytest tests/unit/test_basyx_parser.py tests/unit/test_basyx_builder.py tests/inspection/test_aasx_roundtrip.py -q
```

## Acceptance Criteria
- Roundtrip test passes and shows no missing identifiables.
- Parser strict-mode tests continue to pass.
