# Inspection Specialist: Template Source + Versioning

## Mission

Validate deterministic, auditable upstream template ingestion and refresh behavior.

## Owned Paths

- `backend/app/modules/templates/service.py`
- `backend/app/modules/templates/catalog.py`
- `shared/idta_semantic_registry.json`

## Required Outputs

- Source/version resolution report
- Refresh behavior report (attempted/success/failed/skipped)
- Deprecated/unavailable template policy recommendation

## Acceptance Checks

- Same upstream version must produce deterministic local schema/definition hashes
- Source metadata (path/ref/sha/version) is persisted or surfaced for traceability
- Failure modes distinguish upstream absence vs transport/runtime failures

## Handoff Expectations

- Deliver reproducible commands and API calls used for validation
- List exact contract fields needed by frontend and audit docs
