# Inspection Specialist: IDTA SMT + AAS Metamodel

## Mission

Verify that template interpretation and structure handling align with IDTA SMT and AAS metamodel semantics.

## Owned Paths

- `backend/app/modules/templates/definition.py`
- `backend/app/modules/templates/qualifiers.py`
- `backend/app/modules/aas/`

## Required Outputs

- SMT conformance checklist for supported DPP templates
- Qualifier support matrix (supported, partial, missing)
- Structural fidelity notes for template -> definition conversion

## Acceptance Checks

- No structural drift between template source and generated definition
- Qualifier behavior is either enforced or explicitly flagged as unsupported
- Semantic ID handling is deterministic and test-covered

## Handoff Expectations

- Provide concrete failing/passing cases for each gap
- Include recommended backend/frontend ownership for each fix
