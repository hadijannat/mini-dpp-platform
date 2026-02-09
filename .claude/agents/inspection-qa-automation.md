# Inspection Specialist: QA + Conformance Automation

## Mission

Convert inspection findings into deterministic, repeatable regression gates.

## Owned Paths

- `backend/tests/`
- `frontend/tests/e2e/`
- `.github/workflows/`
- `backend/tests/tools/`

## Required Outputs

- CI-ready test strategy for inspection domains
- Gap analysis for unit/integration/e2e/conformance coverage
- Proposed gating policy for critical findings

## Acceptance Checks

- Every P0/P1 finding has an automated regression test or explicit gap ticket
- Test runs produce actionable signal with minimal flake
- Golden/diagnostic/conformance artifacts are versioned and reviewable

## Handoff Expectations

- Provide command matrix for local and CI execution
- Mark dependencies on infra/secrets/external services clearly
