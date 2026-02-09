# Inspection Specialist: BaSyx + AASX Export

## Mission

Verify export conformance and round-trip safety for AAS representations.

## Owned Paths

- `backend/app/modules/export/service.py`
- `backend/app/modules/aas/conformance.py`
- `backend/tests/conformance/`

## Required Outputs

- Export format conformance report (AASX/JSON/XML/JSON-LD/Turtle as applicable)
- Round-trip verification evidence (export -> import -> semantic comparison)
- Interoperability risks with external AAS tools

## Acceptance Checks

- Exports are parseable and semantically consistent after round-trip
- No silent semantic loss for IDs, qualifiers, value types, or language values
- Conformance checks can be automated in CI

## Handoff Expectations

- Include sample artifacts and command logs
- Identify quick wins vs structural fixes for export reliability
