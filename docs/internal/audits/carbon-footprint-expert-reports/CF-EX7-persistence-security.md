# CF-EX7 Persistence, Provenance, Security and Tenancy

## Owner
Persistence, Provenance, Security and Tenancy Specialist

## Scope
- `/Users/aeroshariati/mini-dpp-platform/backend/app/db/models.py`
- `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/public_router.py`
- `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/submodel_filter.py`
- `/Users/aeroshariati/mini-dpp-platform/backend/tests/inspection/test_provenance_lifecycle.py`
- `/Users/aeroshariati/mini-dpp-platform/backend/tests/inspection/test_security_isolation.py`

## Findings
1. Inspection set lacked dedicated security/tenancy regression coverage for the Carbon Footprint path (`CF-002`).
2. Provenance and revision lifecycle checks needed explicit inspection-level gate coverage.
3. Public environmental exposure required verification against confidentiality and tier filtering rules.

## Implemented
- Added `test_security_isolation.py` for tenant-boundary regression checks.
- Retained and executed lifecycle/provenance inspection tests as required gate evidence.
- Consolidated findings into leader register/backlog with severity and ownership.

## Evidence Command
```bash
uv run pytest tests/inspection/test_provenance_lifecycle.py tests/inspection/test_security_isolation.py -q
```

## Acceptance Criteria
- Template provenance is preserved across immutable revision creation.
- Public routes apply confidentiality/tier filtering without cross-tenant leakage.
- Inspection security and lifecycle tests pass and remain part of Carbon Footprint release gate set.
