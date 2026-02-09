# Remediation Epics (2026-02-09)

Backlog is ordered by closure policy: `P0 -> P1 -> P2`.

## Ordering Rules
- P0 security/data-loss items must be closed before any lower-priority release closure.
- P1 interop/provenance items require automated CI evidence.
- P2 UX/observability items may ship after all open P0/P1 are either resolved or formally accepted risk.

## Epic Backlog

| Epic ID | Priority | Epic Title | Owner Role | Depends On | Target Paths | Acceptance Tests |
|---|---|---|---|---|---|---|
| P0-A | P0 | Strict parser/export correctness and fail-fast errors | Role 1 + Role 3 + Role 5 | None | `backend/app/modules/templates/`, `backend/app/modules/export/` | strict parser tests + export negative-path tests |
| P0-B | P0 | Public access and tier filtering hardening | Role 7 | None | `backend/app/modules/dpps/public_router.py`, `backend/app/modules/dpps/submodel_filter.py` | public access isolation tests |
| P1-A | P1 | Template provenance completeness for all revision creation flows | Role 6 | P0-A | `backend/app/modules/dpps/service.py`, `backend/app/modules/dpps/router.py` | provenance path tests |
| P1-B | P1 | Template refresh API contract clarity + frontend parity | Role 2 + Role 4 | P0-A | `backend/app/modules/templates/router.py`, `frontend/src/features/publisher/pages/` | refresh contract tests + frontend typecheck |
| P1-C | P1 | Dynamic form fidelity for relationship/entity-heavy models | Role 4 + Role 3 | P1-B | `frontend/src/features/editor/`, schema builders | editor validation/e2e tests |
| P1-D | P1 | Automated end-to-end conformance pipeline | Role 8 + Role 5 | P1-A, P1-B, P1-C | `backend/tests/e2e/`, CI workflow config | refresh->create/edit->publish->export->round-trip |
| P2-A | P2 | Unsupported template lifecycle UX and operator guidance | Role 4 + Role 2 | P1-B | templates and create-dialog UIs | UI state and messaging tests |
| P2-B | P2 | Deep AASX content validation beyond archive checks | Role 5 | P1-D | `backend/app/modules/aas/conformance.py` | AASX semantic validation tests |

## Story Templates by Epic

## P0-A Stories
- Add strict error typing for malformed template payloads and export failures.
- Remove/guard any lenient parse branches that can silently drop semantic content.
- Add deterministic error payload contract for parser/export failures.

## P0-B Stories
- Verify deny-by-default behavior for anonymous/public endpoints.
- Enforce published-only data exposure in all public reader paths.
- Add cross-tenant access regression tests for shell/submodel queries.

## P1-A Stories
- Ensure `template_provenance` is written in every new revision path.
- Preserve provenance when cloning/rolling revisions.
- Add migration strategy and fallback behavior for legacy null provenance rows.

## P1-B Stories
- Formalize refresh response counters and deprecation note for `count`.
- Surface support metadata in all template listing endpoints.
- Align frontend selectors and messaging with unsupported/unrefreshable templates.

## P1-C Stories
- Validate relationship/entity/list editing parity with schema semantics.
- Ensure required-language/read-only semantics are enforced consistently.
- Add explicit error display for qualifier-driven validation failures.

## P1-D Stories
- Build CI gate for complete conformance flow (refresh->publish->export->verify).
- Persist compliance artifacts for each CI run.
- Fail pipeline on semantic mismatch or round-trip drift.

## P2-A Stories
- Show support state in template cards and selection dialogs.
- Disable unsupported templates with clear reason text.
- Add operator docs for refresh-disabled templates.

## P2-B Stories
- Extend AASX validation to semantic IDs, qualifiers, and expected value types.
- Add interoperability checks with external AAS tooling where available.
- Emit actionable diagnostics for invalid AASX structures.
