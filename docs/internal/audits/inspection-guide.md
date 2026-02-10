# IDTA Pipeline Inspection Guide

This guide describes the 8-expert inspection framework for validating the Mini DPP Platform's IDTA template pipeline.

## Overview

The inspection validates the complete pipeline:

```
IDTA GitHub → Template Service → Parser → Builder → Schema → Frontend → Persistence → Export
```

**Inspection duration**: 2 hours (parallel execution)
**Expert team**: 8 specialized roles
**Deliverables**: 4 artifacts (Pipeline Map, Findings Register, Alignment Matrix, Execution Plan)

## Quick Start

### 1. Start Inspection Environment

```bash
# Start services (Postgres, Redis, Backend, Keycloak)
docker compose -f docker-compose.inspection.yml up -d

# Wait for backend health check
docker compose -f docker-compose.inspection.yml ps
# backend should show "healthy"
```

### 2. Run Setup Script

```bash
cd backend
uv run python tests/tools/inspection_setup.py
```

This will:
- Fetch all 7 IDTA templates from GitHub
- Generate definition AST and JSON Schema
- Save artifacts to `evidence/run_YYYYMMDD_HHMMSS/`
- Produce `ingestion_summary.json`

### 3. Execute Inspection (Automated)

The inspection runs via Claude Code agent team:

```bash
# In Claude Code session
# The inspection is orchestrated by the team-lead agent
# 8 expert agents run in parallel across 5 phases
```

### 4. Review Deliverables

After 2-hour inspection, review:

```
docs/internal/audits/
├── pipeline-map-2026-02-10.md          # Mermaid flowchart + narrative
├── findings-register-2026-02-10.md     # 23-field finding schema
├── alignment-matrix-2026-02-10.md      # 23 requirements × 7 templates
└── remediation-epics-2026-02-10.md     # Epics → Stories → Tasks
```

## Expert Roles

| Role | Focus Area | Key Deliverable |
|------|------------|-----------------|
| 0: Inspection Lead | Orchestration, synthesis | All 4 deliverables |
| 1: IDTA SMT Specialist | Semantic IDs, qualifiers | `01_idta_smt_specialist.md` |
| 2: Template Versioning | Provenance tracking | `02_template_versioning.md` + tests |
| 3: Parser/Schema | BaSyx fidelity, golden files | `03_parser_schema.md` |
| 4: Frontend Forms | UI rendering, validation | `04_frontend_forms.md` + E2E tests |
| 5: BaSyx Export | 6 formats, conformance | `05_basyx_export.md` + logs |
| 6: Persistence | DB integrity, state machine | `06_persistence_integrity.md` |
| 7: Security | Multi-tenant isolation | `07_security_tenancy.md` |
| 8: QA/Automation | Test coverage, CI/CD | `08_qa_automation.md` |

## Inspection Phases

### Phase 1: Setup (15 min)
**Owner**: Inspection Lead
**Tasks**:
- Start docker-compose.inspection.yml
- Run inspection_setup.py
- Create test data fixtures

**Verification**:
```bash
# Check ingestion summary
cat evidence/run_*/ingestion_summary.json | jq '.templates_succeeded'
# Should be 7 (or 6 if battery-passport upstream not published)
```

### Phase 2: Template Pipeline (25 min, parallel)
**Owners**: Roles 1, 2, 3
**Tasks**:
- Role 1: Semantic ID coverage analysis
- Role 2: Provenance lifecycle validation
- Role 3: Parser fidelity and golden file tests

**Verification**:
```bash
# Check golden files
cd backend
uv run pytest tests/e2e/test_template_goldens.py -v
```

### Phase 3: DPP Lifecycle (35 min, sequential)
**Owners**: Roles 5, 6
**Tasks**:
- Role 6: Create test DPPs, validate DB state (15 min)
- Role 5: Export all formats, run conformance (20 min)

**Verification**:
```bash
# Check conformance tests
uv run pytest tests/conformance/ -v
```

### Phase 4: Frontend (30 min, parallel with Phase 3)
**Owner**: Role 4
**Tasks**:
- Load DPPs in editor
- Screenshot all field types
- Implement qualifier enforcement E2E tests

**Verification**:
```bash
cd frontend
npm run test:e2e -- qualifierEnforcement.spec.ts
```

### Phase 5: Cross-Cutting (20 min, parallel)
**Owners**: Roles 7, 8
**Tasks**:
- Role 7: Security and tenant isolation
- Role 8: Test coverage analysis

**Verification**:
```bash
# Coverage report
cd backend
uv run pytest --cov=app/modules/templates --cov=app/modules/dpps --cov-report=html
```

### Phase 6: Synthesis (15 min)
**Owner**: Role 0
**Tasks**:
- Aggregate 8 expert reports
- Generate 4 deliverables
- Prioritize findings (P0-P3)

## Test Data

Test DPPs are defined in `backend/tests/fixtures/inspection_dpps.json`:

- **minimal_nameplate**: Only required fields
- **full_nameplate**: All optional fields, multilang
- **carbon_footprint**: PCF data
- **technical_data**: Technical specifications
- **hierarchical_structures**: BOM with 3 components
- **battery_passport**: EU Battery Regulation compliant
- **edge_case_empty_collections**: Empty optional collections
- **edge_case_multilang**: 6 languages

## Evidence Collection

All artifacts are saved to `evidence/run_YYYYMMDD_HHMMSS/`:

```
templates/           # Template definition + schema + metadata
dpps/                # Created DPPs + exports + conformance logs
frontend/            # Screenshots + E2E test results
docs/internal/reviews/expert-reports/      # 8 markdown reports
*.json               # Machine-readable data
```

## Deliverable Schemas

### 1. Findings Register

23-field schema per finding:

```
ID, Status, Severity (P0-P3), Category, Expert Reviewer, Reproducibility,
Affected Paths[], User Impact, Compliance Impact, Evidence{}, Root Cause,
Recommended Fix, Estimated Effort, Dependencies[], Owner Role, Collaborators[],
Regression Test, Related PRs[], Created Date, Updated Date
```

Evidence object:
```json
{
  "reproduction_command": "uv run pytest tests/...",
  "observed_output": "...",
  "log_artifact_path": "/evidence/.../failure.log",
  "screenshot_path": null,
  "diff_snippet": {...},
  "audit_tool_output": {...}
}
```

### 2. Alignment Matrix

23 requirements × 7 templates grid:

**Status symbols**:
- ✅ Aligned
- ⚠️ Partially Aligned (with gap count)
- ❌ Gap
- N/A Not Applicable

**Evidence symbols**:
- UT (unit test)
- IT (integration test)
- GF (golden file)
- CT (conformance tool)
- MV (manual verification)
- AT (audit tool)

### 3. Execution Plan

Epic → Story → Task hierarchy:

**Epic schema**:
```
ID, Priority, Title, Theme, Owner Role, Dependencies[], Target Paths[],
Acceptance Criteria[], Story Count, Total Effort, Findings Addressed[]
```

**Themes**:
- Template Provenance
- Qualifier Completeness
- Frontend UX
- Export Conformance
- Observability

## Success Criteria

- [ ] All 7 templates ingested (battery-passport may fail if upstream not published)
- [ ] Golden file tests pass (6/6 for existing templates)
- [ ] Audit tool shows <5 critical gaps per template
- [ ] Provenance tracked in 100% of revision lifecycle
- [ ] AASX round-trip identical structure
- [ ] 10+ qualifier types enforced in frontend
- [ ] Alignment Matrix ≥70% "Aligned" cells
- [ ] No P0 findings in final register

## Troubleshooting

### Backend won't start

```bash
# Check logs
docker compose -f docker-compose.inspection.yml logs backend

# Common issues:
# - Postgres not healthy: wait 30s for init
# - Migration error: check DATABASE_URL env var
# - Port conflict: change ports in docker-compose.inspection.yml
```

### Template ingestion fails

```bash
# Check GitHub connectivity
curl -I https://api.github.com

# Check logs
cd backend
uv run python tests/tools/inspection_setup.py 2>&1 | tee ingestion.log

# Common issues:
# - Rate limit: wait 1 hour or use GitHub token
# - Template not found: check catalog.py source_file paths
# - Parse error: check BaSyx parser failsafe=False enforcement
```

### Conformance tests fail

```bash
# Install aas-test-engines
cd backend
uv pip install aas-test-engines

# Run manually
uv run pytest tests/conformance/ -v --tb=short

# Common issues:
# - Export format invalid: check failsafe boundary
# - Missing modelType: BaSyx serialization issue
# - IRI encoding: check Turtle percent-encoding
```

## References

- Inspection Charter: `docs/internal/audits/inspection-charter-2026-02-09.md`
- Agent Playbook: `docs/internal/agent-teams/aas-dpp-inspection-squad-playbook.md`
- IDTA Specs: https://github.com/admin-shell-io/submodel-templates
- AAS Metamodel: IDTA-01001 (Part 1)
- AASX Package: IDTA-01005 (Part 5)
