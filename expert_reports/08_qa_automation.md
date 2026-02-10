# Expert Report #8: QA & Automation Coverage Analysis

**Inspector**: QA/Automation Engineer
**Scope**: Test coverage, CI/CD pipelines, test markers, golden file processes
**Date**: 2026-02-10

---

## 1. Executive Summary

The Mini DPP Platform has a **solid foundation** of 1,074 backend tests and 254 frontend tests with well-structured CI/CD. However, coverage analysis reveals **significant gaps** in core business logic modules (DPP service: 40%, template service: 29%, basyx_builder: 18%) while peripheral utilities enjoy 90-100% coverage. The CI pipeline is well-designed with 8 parallel jobs, but lacks coverage enforcement thresholds and test parallelization.

**Overall risk**: MEDIUM — The most critical paths (DPP create/edit/publish, template definition building) have the lowest unit test coverage. Integration/E2E tests partially compensate, but those require Docker Compose infrastructure and don't run in the fast CI path.

---

## 2. Coverage Metrics

### 2.1 Templates + DPPs Module Coverage (Primary Scope)

| File | Stmts | Miss | Coverage | Risk |
|------|-------|------|----------|------|
| `templates/definition.py` | 138 | 114 | **17%** | CRITICAL |
| `dpps/basyx_builder.py` | 319 | 263 | **18%** | CRITICAL |
| `templates/service.py` | 444 | 315 | **29%** | HIGH |
| `dpps/service.py` | 569 | 365 | **36%** | HIGH |
| `templates/diagnostics.py` | 165 | 98 | **41%** | MEDIUM |
| `dpps/router.py` | 337 | 197 | **42%** | MEDIUM |
| `templates/qualifiers.py` | 160 | 65 | **59%** | MEDIUM |
| `dpps/repository.py` | 59 | 18 | **70%** | LOW |
| `templates/router.py` | 136 | 40 | **71%** | LOW |
| `templates/basyx_parser.py` | 61 | 16 | **74%** | LOW |
| `dpps/public_router.py` | 169 | 39 | **77%** | LOW |
| `templates/catalog.py` | 47 | 7 | **85%** | LOW |
| `templates/schema_from_definition.py` | 216 | 4 | **98%** | NONE |
| `dpps/submodel_filter.py` | 30 | 0 | **100%** | NONE |
| `dpps/idta_schemas.py` | 33 | 0 | **100%** | NONE |
| **TOTAL (Templates + DPPs)** | **2,887** | **1,541** | **47%** | |

### 2.2 Overall Project Coverage

| Metric | Value |
|--------|-------|
| **Total statements** | 10,364 |
| **Covered statements** | 6,303 |
| **Overall coverage** | **61%** |
| **Backend test count** | 1,074 |
| **Frontend test count** | 254 |
| **Total tests** | 1,328 |

### 2.3 Critically Under-Tested Files (<30% coverage, >50 statements)

| File | Stmts | Coverage | Gap Description |
|------|-------|----------|-----------------|
| `templates/definition.py` | 138 | 17% | AST builder — the core of template→form pipeline |
| `dpps/basyx_builder.py` | 319 | 18% | BaSyx AAS environment builder — DPP serialization core |
| `connectors/catenax/service.py` | ~100 | 24% | Catena-X DTR integration |
| `connectors/edc/contract_service.py` | ~80 | 24% | EDC contract negotiation |
| `audit/router.py` | 111 | 27% | Audit trail endpoints |
| `webhooks/service.py` | ~60 | 28% | Webhook delivery logic |
| `templates/service.py` | 444 | 29% | Template registry service (GitHub fetch, caching, refresh) |
| `lca/extractor.py` | ~50 | 14% | LCA material extraction |
| `masters/service.py` | ~70 | 17% | DPP Masters service |
| `export/router.py` | ~90 | 30% | Export endpoint handlers |

### 2.4 Well-Tested Files (>80% coverage)

| File | Coverage | Notes |
|------|----------|-------|
| `aas/serialization.py` | 100% | Full JSON-LD/Turtle coverage (PR #48, #52) |
| `templates/schema_from_definition.py` | 98% | Schema generation thoroughly tested |
| `core/audit.py` | 98% | Hash chain + advisory locks |
| `core/crypto/*` | 100% | All crypto modules fully covered |
| `dpps/submodel_filter.py` | 100% | ESPR tier filtering |
| `compliance/engine.py` | 89% | ESPR rule evaluation |

---

## 3. CI/CD Pipeline Analysis

### 3.1 CI Pipeline (`ci.yml`) — 8 Jobs

| Job | Purpose | Execution | Status |
|-----|---------|-----------|--------|
| `backend-lint` | Ruff + mypy | Sequential | GOOD |
| `backend-test` | pytest + coverage → Codecov | Needs Postgres + Redis | GOOD |
| `backend-security` | Bandit SAST + pip-audit | Sequential | GOOD |
| `frontend-lint` | ESLint + TypeScript | Sequential | GOOD |
| `frontend-test` | Vitest | Sequential | GOOD |
| `frontend-security` | npm audit | Sequential | GOOD |
| `aas-validation` | BaSyx golden fixture validation | Sequential | GOOD |
| `helm-lint` | Helm lint + template | Sequential | GOOD |
| `build` | Docker image build (no push) | Depends on all above | GOOD |

**Architecture**: First 8 jobs run in parallel, `build` job gates on all passing. This is optimal.

### 3.2 DPP Pipeline (`dpp-pipeline.yml`) — 1 Job

| Step | Purpose | Status |
|------|---------|--------|
| Docker Compose stack startup | Full environment | GOOD |
| Backend health wait | Retry loop, 30 attempts | GOOD |
| Keycloak realm wait | 60 attempts × 3s = 180s timeout | GOOD |
| E2E + Golden tests | `pytest -m "e2e or golden"` | GOOD |
| Container log dump | On failure | GOOD |
| Artifact upload | Always | GOOD |
| Teardown | `docker compose down -v` | GOOD |

### 3.3 Deploy Pipeline (`deploy.yml`)

| Feature | Status |
|---------|--------|
| CI gate (workflow_run) | GOOD — blocks on CI success |
| Trivy vulnerability scanning | GOOD — blocks on HIGH/CRITICAL |
| Migration rollback | GOOD — reverts on failure |
| Health check (internal) | GOOD — 30 retries × 10s |
| Health check (public) | GOOD — verifies `/health` endpoint |
| Frontend SHA verification | GOOD — confirms correct build deployed |
| BuildKit cache resilience | GOOD — `ignore-error=true` on cache-to |

### 3.4 CI Gaps Identified

| Gap | Severity | Description |
|-----|----------|-------------|
| **No coverage threshold** | HIGH | CI uploads coverage to Codecov but doesn't fail on regression. A PR could drop coverage from 61% to 30% and still pass. |
| **No pytest-xdist** | MEDIUM | 1,074 tests run single-threaded in ~4.6s locally. Not critical yet, but will become bottleneck as test count grows. |
| **Integration tests broken locally** | MEDIUM | 11 integration tests (`test_dpp_lifecycle.py`) fail locally (need PostgreSQL on port 5433). They pass in CI with services but this creates a gap in local dev feedback. |
| **Conformance tests not in CI** | LOW | Only 4 conformance tests exist and aren't run in either CI or DPP Pipeline (they need `--run-conformance` marker flag or special env). |
| **No frontend coverage** | LOW | Frontend runs tests but doesn't collect/report coverage metrics. |
| **E2E tests only in DPP Pipeline** | INFO | 28 E2E tests only run in `dpp-pipeline.yml`, not `ci.yml`. This is by design (they need Docker Compose) but means PR feedback loop lacks E2E validation. |

---

## 4. Test Marker Analysis

### 4.1 Registered Markers

| Marker | Count | Used In | CI Integration |
|--------|-------|---------|----------------|
| `e2e` | 28 tests | `tests/e2e/` | DPP Pipeline (`-m "e2e or golden"`) |
| `golden` | 1 test | `test_template_goldens.py` | DPP Pipeline |
| `conformance` | 4 tests | `tests/conformance/` | **NOT IN CI** |

### 4.2 Marker Usage Assessment

- **`e2e`**: Properly applied to all 28 E2E tests. Gate: `--run-e2e` or `RUN_E2E=1`. Consistent.
- **`golden`**: Only 1 test (template hash validation). Also has `e2e` marker. Gate: `--run-goldens` or `RUN_GOLDENS=1`. Consistent.
- **`conformance`**: 4 tests for AAS conformance validation. **NOT gated by a custom flag** — uses standard `@pytest.mark.conformance` but no skip logic. Tests are in `tests/conformance/` and only run when explicitly selected with `-m conformance`.
- **Missing markers**: EPCIS flow tests have `@pytest.mark.e2e` but `test_epcis_flow.py` has individual test functions without the class marker — 22 tests are skipped via `conftest.py` skip logic, not via the marker.

### 4.3 Unregistered Custom Markers

No unregistered markers found. The 3 markers (`e2e`, `golden`, `conformance`) are properly registered in `pyproject.toml` `[tool.pytest.ini_options].markers`.

---

## 5. Golden File Process Assessment

### 5.1 Current Process

1. **Hash computation**: `uv run python tests/tools/compute_golden_hashes.py` — fetches all 7 IDTA templates from GitHub and computes definition + schema SHA-256 hashes
2. **Storage**: `backend/tests/goldens/templates/*.json`
3. **Validation**: `test_template_goldens.py` compares runtime hashes against stored values
4. **Update**: `uv run python tests/tools/update_template_goldens.py` (convenience wrapper)

### 5.2 Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Documentation** | GOOD | CLAUDE.md documents the process, tools, and when to update |
| **Ease of update** | GOOD | Single command to recompute all hashes |
| **CI integration** | GOOD | Runs in DPP Pipeline with `RUN_GOLDENS=1` |
| **Network dependency** | RISK | Requires GitHub API access. Pinned to commit `1d4e0b45469f...` in CI for reproducibility |
| **Battery passport gap** | KNOWN | Golden file missing for IDTA 02035 (not yet published upstream). Documented in CLAUDE.md |
| **First-failure stop** | RISK | Test stops at first hash mismatch — doesn't report all failures at once. Could be improved with `@pytest.mark.parametrize` |

---

## 6. Test Parallelization Opportunities

### 6.1 Backend

| Opportunity | Effort | Impact |
|-------------|--------|--------|
| Add `pytest-xdist` for `-n auto` | LOW | ~2-3x speedup on multi-core CI runners (current: 4.6s → ~1.5s). Minimal impact now, significant when test suite grows. |
| Split `test_dpp_lifecycle.py` integration tests to use in-memory SQLite | MEDIUM | Would eliminate 11 local errors and speed up integration testing |
| Parametrize golden file tests (1 per template) | LOW | Better failure reporting — see all broken templates at once instead of stopping at first |

### 6.2 Frontend

| Opportunity | Effort | Impact |
|-------------|--------|--------|
| Vitest already parallel by default | N/A | 254 tests in 2.3s — no improvement needed |
| Add `--coverage` to `npm test` | LOW | Would enable coverage tracking (currently absent) |

### 6.3 CI Pipeline

| Opportunity | Effort | Impact |
|-------------|--------|--------|
| Current 8-job parallel structure | N/A | Already optimal — all lint/test/security run in parallel |
| Add conformance tests as separate CI job | MEDIUM | Would catch AAS spec regressions in PRs, not just DPP Pipeline |
| Cache uv dependencies | LOW | `uv sync` is fast but caching would save ~5-10s per job |

---

## 7. Specific Coverage Gaps in Critical Paths

### 7.1 `templates/definition.py` (17% — CRITICAL)

**What's untested**: The BaSyx→AST builder (`build_definition_from_parsed()`) that transforms parsed BaSyx model into `DefinitionNode` tree. This is the **core of the entire template pipeline** — every DPP form starts here.

**Missing coverage**:
- Lines 30-41: Entity handling
- Lines 51-61: Collection/list construction
- Lines 64-68: Annotation handling
- Lines 88-166: Main dispatch logic for all SMC types
- Lines 169-178, 182-206: Property type mapping
- Lines 219-256: Qualifier extraction and enrichment

**Why it matters**: Changes to this file can silently break the entire DPP editor for all 7 templates. Currently relies on E2E pipeline tests and golden file hashes for regression detection.

### 7.2 `dpps/basyx_builder.py` (18% — CRITICAL)

**What's untested**: The BaSyx AAS environment builder that constructs full AAS shells, asset information, and submodels from DPP data. Used in create, update, and publish flows.

**Missing coverage**:
- Lines 40-83: Shell/asset construction
- Lines 94-555: All submodel building, property setting, collection assembly

**Why it matters**: Malformed AAS environments would break all export formats (JSON, AASX, JSON-LD, Turtle) and external registry integration.

### 7.3 `dpps/service.py` (40% — HIGH)

**What's untested**:
- `_create_dpp()` (lines 97-167): DPP creation with template resolution and provenance
- `_update_dpp()` (lines 190-198): Update flow
- `_rebuild_dpp_from_templates()` (lines 240-256): Template rebuild with fresh provenance
- `_publish_dpp()` (lines 322-334): Publish flow (state guard + auto-register)
- `_archive_dpp()` (lines 342-346): Archive flow
- Batch import (lines 946-1022)
- Revision history/diff (lines 1139-1201)

### 7.4 Error Paths Not Tested

| Module | Untested Error Path |
|--------|-------------------|
| `templates/service.py` | GitHub API failure during template fetch |
| `templates/service.py` | Invalid BaSyx parse (malformed IDTA JSON) |
| `dpps/router.py` | Concurrent DPP update conflict (409) |
| `dpps/service.py` | Template not found during DPP creation |
| `export/router.py` | Export of non-existent DPP |
| `basyx_builder.py` | Malformed submodel data handling |
| `public_router.py` | Invalid Base64 in shell/submodel ID URLs |

---

## 8. Recommendations

### 8.1 Immediate (Before Next Release)

| # | Action | Priority | Effort |
|---|--------|----------|--------|
| 1 | **Add coverage threshold to CI** (`--cov-fail-under=55`) | HIGH | 1 line in `ci.yml` |
| 2 | **Add unit tests for `definition.py`** — test AST builder with mock BaSyx objects | HIGH | 2-4 hours |
| 3 | **Add unit tests for `basyx_builder.py`** — test AAS environment construction | HIGH | 3-5 hours |
| 4 | **Parametrize golden file test** — one test case per template | LOW | 30 min |
| 5 | **Add conformance tests to CI** — new job in `ci.yml` | MEDIUM | 1 hour |

### 8.2 Short-Term (Next Sprint)

| # | Action | Priority | Effort |
|---|--------|----------|--------|
| 6 | **Add `pytest-xdist`** for parallel test execution | MEDIUM | 1 hour |
| 7 | **Fix integration test local dev experience** — add SQLite fallback or `.env.test` | MEDIUM | 2 hours |
| 8 | **Add frontend coverage reporting** (`vitest --coverage`) | LOW | 1 hour |
| 9 | **Add DPP service unit tests** — mock DB, test create/update/publish/archive paths | HIGH | 4-6 hours |
| 10 | **Add template service unit tests** — mock httpx, test fetch/cache/refresh logic | MEDIUM | 3-4 hours |

### 8.3 Long-Term

| # | Action | Priority |
|---|--------|----------|
| 11 | Implement property-based testing for AAS serialization round-trips (hypothesis) |  MEDIUM |
| 12 | Add mutation testing (`mutmut`) to assess test effectiveness | LOW |
| 13 | Add performance benchmarks for template pipeline (pytest-benchmark) | LOW |

---

## 9. Findings Summary

| ID | Finding | Severity | Category |
|----|---------|----------|----------|
| QA-001 | `definition.py` at 17% coverage — core template pipeline untested | CRITICAL | Coverage Gap |
| QA-002 | `basyx_builder.py` at 18% coverage — AAS builder untested | CRITICAL | Coverage Gap |
| QA-003 | `templates/service.py` at 29% — template registry service barely tested | HIGH | Coverage Gap |
| QA-004 | `dpps/service.py` at 40% — DPP lifecycle service under-tested | HIGH | Coverage Gap |
| QA-005 | No CI coverage threshold — regressions go undetected | HIGH | CI Gap |
| QA-006 | 11 integration tests broken without local PostgreSQL | MEDIUM | Dev Experience |
| QA-007 | Conformance tests (4) not in CI pipeline | MEDIUM | CI Gap |
| QA-008 | No frontend coverage reporting | LOW | Visibility |
| QA-009 | Golden file test stops at first failure | LOW | Test Design |
| QA-010 | No test parallelization (`pytest-xdist`) | LOW | Performance |

---

## 10. Test Execution Timing

| Suite | Tests | Duration | Per-Test Avg |
|-------|-------|----------|--------------|
| Backend unit (local) | 1,008 | 4.6s | 4.6ms |
| Backend unit (CI estimate) | 1,008 | ~8-12s | ~10ms |
| Frontend (local) | 254 | 2.3s | 9.1ms |
| E2E + Golden (CI Docker Compose) | 28 + 1 | ~60-120s | ~2-4s |
| Conformance | 4 | ~5s | ~1.25s |

**Observation**: Backend unit tests are remarkably fast (4.6s for 1,008 tests). The bottleneck is the DPP Pipeline's Docker Compose startup time (~3-5 min including Keycloak), not test execution.

---

*Report generated: 2026-02-10*
*Coverage data: `expert_reports/coverage_report.json`*
