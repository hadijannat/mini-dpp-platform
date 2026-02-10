# AAS/DPP Inspection Squad Playbook (8 Experts + 1 Lead)

**As of:** 2026-02-09

This playbook defines a decision-complete, role-based execution model for auditing and improving the IDTA template-driven AAS/DPP pipeline in this repository.

## 1) Mission

Produce a full, evidence-backed inspection of:

- IDTA template ingestion and versioning
- Parser/definition/schema fidelity
- Frontend qualifier enforcement
- DPP persistence and provenance
- AASX export and round-trip conformance
- Public viewer security and tenancy boundaries
- QA and conformance automation coverage

## 2) Team Topology

- **Role 0:** Inspection Lead
- **Role 1:** IDTA SMT + AAS Metamodel Specialist
- **Role 2:** Template Source + Versioning Engineer
- **Role 3:** Backend Parser + Schema Engineer
- **Role 4:** Frontend Dynamic Forms Engineer
- **Role 5:** BaSyx + AASX Compliance Engineer
- **Role 6:** Persistence + Data Integrity Engineer
- **Role 7:** Security + Multi-tenancy Engineer
- **Role 8:** QA + Conformance Automation Engineer

## 3) Deliverables Matrix

| Artifact | Owner | Purpose |
|---|---|---|
| Pipeline map (stages + artifacts + boundaries) | Lead | Establish shared system model |
| Findings register | Lead (all contributors) | Track severity, evidence, owners, fixes |
| Alignment matrix | Lead + domain experts | Map requirements vs implementation evidence |
| Remediation epics | Lead + experts | Turn findings into dependency-ordered backlog |

Use existing repo destinations:

- `docs/internal/audits/findings-register-*.md`
- `docs/internal/audits/alignment-matrix-*.md`
- `docs/internal/audits/remediation-epics-*.md`

## 4) Role Charters

### Role 0: Inspection Lead

- Owns synthesis, severity, and decision log.
- Enforces evidence quality and file ownership rules.
- Approves plan transitions between phases.

### Role 1: IDTA SMT + AAS Specialist

- Verifies `kind=Template`, semantic IDs, qualifier semantics, structure fidelity.
- Focus paths:
  - `backend/app/modules/templates/definition.py`
  - `backend/app/modules/templates/qualifiers.py`
  - `backend/app/modules/aas/`

### Role 2: Template Source + Versioning

- Verifies upstream selection policy (`published/` vs `deprecated/`) and deterministic refresh behavior.
- Focus paths:
  - `backend/app/modules/templates/service.py`
  - `backend/app/modules/templates/catalog.py`
  - `shared/idta_semantic_registry.json`

### Role 3: Parser + Schema

- Verifies AST/schema fidelity and diagnostics output completeness.
- Focus paths:
  - `backend/app/modules/templates/basyx_parser.py`
  - `backend/app/modules/templates/schema_from_definition.py`
  - `backend/app/modules/templates/diagnostics.py`

### Role 4: Frontend Dynamic Forms

- Verifies schema-to-UI contract and qualifier enforcement UX.
- Focus paths:
  - `frontend/src/features/editor/`

### Role 5: BaSyx + AASX Compliance

- Verifies export correctness and semantic round-trip preservation.
- Focus paths:
  - `backend/app/modules/export/service.py`
  - `backend/app/modules/aas/conformance.py`

### Role 6: Persistence + Integrity

- Verifies revision reproducibility, provenance, auditability, and encryption boundaries.
- Focus paths:
  - `backend/app/db/models.py`
  - `backend/app/modules/dpps/service.py`
  - `backend/app/db/migrations/`

### Role 7: Security + Multi-tenancy

- Verifies tenant isolation and public-view authorization/tier behavior.
- Focus paths:
  - `backend/app/modules/dpps/public_router.py`
  - `backend/app/modules/dpps/submodel_filter.py`
  - `backend/app/core/security/`
  - `infra/opa/policies/dpp_authz.rego`

### Role 8: QA + Automation

- Converts findings into stable CI checks and regression suites.
- Focus paths:
  - `backend/tests/`
  - `frontend/tests/e2e/`
  - `.github/workflows/`

## 5) Execution Sequence

1. **Baseline and environment health**
- Bring stack up, run migrations, verify template endpoints and auth.

2. **Template ingestion evidence**
- Capture source selection, version resolution, SHA/hash metadata behavior.

3. **Schema and diagnostics validation**
- Run diagnostics and record coverage/gap artifacts.

4. **UI rendering and validator behavior**
- Verify cardinality/range/readonly/multilang/either-or behaviors.

5. **Persistence and revision reproducibility**
- Verify template/schema provenance and revision consistency.

6. **Export and round-trip conformance**
- Export AASX/JSON and verify semantic equivalence after re-import.

7. **Update scenario hardening**
- Re-run refresh/update scenarios and confirm deterministic diffs + gating.

## 6) Acceptance Criteria by Role

- Every finding includes: severity, reproducibility, evidence, root cause hypothesis, recommended fix, regression test.
- All P0/P1 items have explicit owners and dependency-aware remediation order.
- No item marked resolved without current test evidence.
- Final matrix states `Aligned`, `Partially Aligned`, or `Gap` per requirement.

## 7) Exit Criteria for "Inspection Complete"

- Findings register published and internally consistent.
- Alignment matrix complete for all in-scope requirements.
- Remediation epics documented with dependency chain.
- No unresolved ambiguity on ownership of open P0/P1 findings.
- CI/test strategy defined for preventing recurrence.

## 8) Suggested Working Commands

```bash
# Example baseline checks
cd backend
uv run pytest tests/unit/test_template_service.py tests/unit/test_export_service.py -q
uv run pytest tests/unit/test_public_dpp.py tests/unit/test_espr_tiered_access.py -q

cd ../frontend
npm run test -- --run src/features/viewer/pages/__tests__/DPPViewerPage.test.tsx
npm run typecheck
```

## 9) Operating Rules

- One owner per file area during implementation.
- Evidence-first findings only; no assertion without proof.
- Prefer additive, backward-compatible changes for API/data contracts.
- Keep docs and tests updated with every remediated finding.
