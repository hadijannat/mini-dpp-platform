# Fresh AAS/DPP Inspection Charter (2026-02-09)

## Objective
- Execute a fresh, full, evidence-backed audit of the template-driven pipeline:
  `IDTA SMT -> backend parser/schema -> frontend editor -> DPP revisions -> export/conformance`.
- Produce a decision-ready remediation backlog with explicit owners, dependencies, and test gates.
- Treat prior audit artifacts as historical context; final status is based on current `main` behavior only.

## Standards Baseline
- IDTA AAS Part 1 (metamodel).
- IDTA AAS Part 2 (API profile and repository semantics).
- IDTA AAS Part 5 (AASX packaging/interchange).
- IDTA DPP4.0 submodel template baseline used by this repository.

## Scope
- Template source and version resolution behavior.
- Template parser fidelity and schema determinism.
- Frontend dynamic renderer and qualifier enforcement.
- DPP revision provenance and persistence integrity.
- Public viewer access control and tier filtering.
- Export pipeline: JSON, AASX, XML, JSON-LD, Turtle.
- CI conformance gates and regression automation.

## Out of Scope
- Infrastructure redesign (deployment/runtime topology).
- Non-DPP feature expansion (connectors, credentials, EPCIS enhancements) unless directly required to close a compliance gap.

## Team Topology and File Ownership
- `Role 0: Inspection Leader` -> `/Users/aeroshariati/mini-dpp-platform/docs/audits/`
- `Role 1: IDTA/AAS Specialist` ->
  `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/definition.py`,
  `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/qualifiers.py`,
  `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/aas/`
- `Role 2: Source/Versioning Engineer` ->
  `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/service.py`,
  `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/catalog.py`,
  `/Users/aeroshariati/mini-dpp-platform/shared/idta_semantic_registry.json`
- `Role 3: Parser/Schema Engineer` ->
  `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/basyx_parser.py`,
  `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/schema_from_definition.py`
- `Role 4: Frontend Dynamic Forms Engineer` ->
  `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/editor/`
- `Role 5: BaSyx/AASX Export Engineer` ->
  `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/export/service.py`,
  `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/aas/conformance.py`
- `Role 6: Persistence/Integrity Engineer` ->
  `/Users/aeroshariati/mini-dpp-platform/backend/app/db/models.py`,
  `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/service.py`,
  migrations
- `Role 7: Security/Tenancy Engineer` ->
  `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/public_router.py`,
  `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/submodel_filter.py`,
  ABAC/OPA references
- `Role 8: QA/Automation Engineer` ->
  `/Users/aeroshariati/mini-dpp-platform/backend/tests/`,
  `/Users/aeroshariati/mini-dpp-platform/frontend/tests/e2e/`,
  CI workflow gates

## Severity Rubric
- `P0` Blocker: security boundary break, cross-tenant data leak, silent data loss, non-recoverable provenance loss.
- `P1` High: interop/compliance failure, non-deterministic template behavior, export mismatch with semantic loss.
- `P2` Medium: user-facing validation drift, partial contract inconsistency, missing observability/gates.
- `P3` Low: cosmetic or non-blocking documentation/tooling gaps.

## Evidence Rules
- Every finding must include:
  - reproduction command/API call,
  - observed output/log artifact,
  - impacted file paths,
  - failing/passing test reference,
  - remediation proposal with acceptance test.
- No finding is accepted without at least one direct code or runtime artifact.
- Historical findings are auto-reconciled:
  - mark `Resolved` only if current code + tests prove closure,
  - otherwise keep `Open` with fresh evidence.

## Execution Protocol
1. Phase 1: parallel read-only inspection by specialist roles.
2. Phase 2: leader consolidation into one matrix (`Aligned`, `Partially Aligned`, `Gap`).
3. Phase 3: remediation epics/tasks in strict order:
   - `P0 security/data-loss`,
   - `P1 provenance/interop`,
   - `P2 UX/observability`.

## Delivery Artifacts
- `inspection-charter-2026-02-09.md` (this file).
- `findings-register-2026-02-09.md`.
- `alignment-matrix-2026-02-09.md`.
- `remediation-epics-2026-02-09.md`.
- `remediation-epics-2026-02-09.csv` (Linear/Jira import starter).

## Sign-Off Checklist
- [ ] All in-scope domains audited against standards baseline.
- [ ] Every open finding has severity, owner-role, and regression test.
- [ ] No P0/P1 closure without automated CI evidence.
- [ ] API contract changes are additive first and backward-compatible for one release cycle.
- [ ] Backlog ordering frozen by severity/dependency rules.
