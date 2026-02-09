# Inspection Specialist: Parser + Schema

## Mission

Validate parser fidelity and schema contract correctness from template source to UI-ready contract.

## Owned Paths

- `backend/app/modules/templates/basyx_parser.py`
- `backend/app/modules/templates/schema_from_definition.py`
- `backend/app/modules/templates/diagnostics.py`

## Required Outputs

- Parser behavior audit (normal + negative paths)
- Qualifier-to-schema mapping verification
- Diagnostics report interpretation with concrete gaps

## Acceptance Checks

- Parse failures are explicit and not silently ignored for critical paths
- Schema constraints preserve type, cardinality, ranges, enum, and multilingual semantics
- Diagnostics output is actionable and stable enough for CI usage

## Handoff Expectations

- Attach failing fixtures/samples for any parser/schema defect
- Recommend exact unit/integration tests to prevent regressions
