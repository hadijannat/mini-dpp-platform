# Findings Register Template (2026-02-09)

Use this register for all fresh inspection findings. Historical findings must be re-validated before carry-over.

## Status Legend
- `Open`: verified in current code/runtime.
- `Resolved`: closure proven by current tests/evidence.
- `Accepted Risk`: intentionally deferred with explicit approver and expiry review date.

## Findings

| ID | Status | Severity | Category | Reproducibility | Affected Paths | User/Compliance Impact | Evidence | Root Cause Hypothesis | Recommended Fix | Owner Role | Regression Test |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AUD-0001 | Resolved | P1 | Template Ingestion/API Contract | Always | `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/router.py` | Refresh endpoint lacked explicit attempted/success/failed/skipped counters for auditability. | `uv run pytest tests/unit/test_templates_router_contract.py -q` | Refresh response only returned aggregate `count`, reducing operator visibility. | Added counter fields and preserved `count` as compatibility alias. | Role 2 | `/Users/aeroshariati/mini-dpp-platform/backend/tests/unit/test_templates_router_contract.py` |
| AUD-0002 | Resolved | P1 | Template Catalog/UI Contract | Always | `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/router.py`, `/Users/aeroshariati/mini-dpp-platform/frontend/src/features/publisher/pages/TemplatesPage.tsx` | Clients could not differentiate unsupported/unrefreshable templates in list views. | `uv run pytest tests/unit/test_templates_router_contract.py -q`; `npm --prefix frontend run typecheck` | Template list payload omitted support metadata exposed by semantic registry. | Added `support_status` + `refresh_enabled` in template payloads and surfaced state in frontend cards/forms. | Role 2 + Role 4 | `/Users/aeroshariati/mini-dpp-platform/backend/tests/unit/test_templates_router_contract.py` |
| AUD-0003 | Resolved | P0 | Persistence/Revision Provenance | Always | `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/service.py`, `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/dpps/router.py` | New revisions could lose template provenance in import/update/rebuild/publish paths, weakening reproducibility. | `uv run pytest tests/unit/test_dpp_provenance_paths.py -q` | Revision creation paths copied nullable provenance without default fallback. | Normalized provenance to `{}` for new revision paths and serialized in revision responses. | Role 6 | `/Users/aeroshariati/mini-dpp-platform/backend/tests/unit/test_dpp_provenance_paths.py` |
| AUD-0004 | Open | P1 | QA/Conformance Automation | Always | `/Users/aeroshariati/mini-dpp-platform/backend/tests/e2e/test_dpp_pipeline.py` | Full pipeline conformance test exists but is skipped unless explicit e2e flag is enabled. | `uv run pytest tests/e2e/test_dpp_pipeline.py::test_pipeline_refresh_build_export -q` (skipped: requires `--run-e2e`) | CI does not enforce full refresh->publish->export flow by default test invocation. | Wire e2e conformance suite into gated CI job with `RUN_E2E=1` and artifact retention. | Role 8 | `/Users/aeroshariati/mini-dpp-platform/backend/tests/e2e/test_dpp_pipeline.py` |

## Mandatory Field Rules
- `ID`: stable key (`AUD-####`) used in issues/PRs.
- `Severity`: one of `P0/P1/P2/P3` only.
- `Reproducibility`: `Always`, `Intermittent`, or `Unknown`.
- `Affected Paths`: repository paths (comma-separated if multiple).
- `Evidence`: direct artifact references (command output, report file, failing test).
- `Regression Test`: exact test file/test id to prevent reintroduction.

## Triage Notes
- Reclassify severity only with documented rationale.
- If a finding spans multiple domains, keep one primary owner-role and add collaborators in the issue.
- If closure requires an API contract change, include compatibility window and migration note.
