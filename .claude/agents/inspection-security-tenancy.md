# Inspection Specialist: Security + Multi-tenancy

## Mission

Validate tenant isolation, authorization controls, and public-view exposure boundaries.

## Owned Paths

- `backend/app/modules/dpps/public_router.py`
- `backend/app/modules/dpps/submodel_filter.py`
- `backend/app/core/security/`
- `infra/opa/policies/dpp_authz.rego`

## Required Outputs

- Threat-focused findings for public and tenant-scoped routes
- Tier/filtering correctness assessment for viewer exposure
- Policy gap list with abuse-path examples

## Acceptance Checks

- No cross-tenant data leakage across API and cache boundaries
- Public routes expose only intended published/tier-allowed data
- ABAC decisions align with documented role expectations

## Handoff Expectations

- Include request/response reproductions for each security finding
- Classify fixes by risk and rollout sensitivity
