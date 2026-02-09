# Inspection Specialist: Persistence + Data Integrity

## Mission

Verify reproducibility and integrity of DPP revisions, provenance, and sensitive data handling.

## Owned Paths

- `backend/app/db/models.py`
- `backend/app/modules/dpps/service.py`
- `backend/app/db/migrations/`
- `backend/app/core/encryption.py`

## Required Outputs

- Revision data model assessment
- Provenance persistence check (template/schema references)
- Integrity and auditability findings

## Acceptance Checks

- Published and historical revisions are reproducible from stored metadata
- Provenance fields are preserved across create/update/rebuild/publish flows
- Sensitive fields respect stated encryption and audit boundaries

## Handoff Expectations

- Provide migration/data-compat implications for each fix
- Propose regression tests for lifecycle and provenance paths
