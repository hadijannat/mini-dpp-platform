# CF-EX5 PCF Domain and Parameter Proposal

## Owner
PCF Domain and Parameter Proposal Specialist

## Scope
- `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/lca/extractor.py`
- `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/lca/engine.py`
- `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/lca/service.py`
- `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/lca/router.py`
- `/Users/aeroshariati/mini-dpp-platform/backend/app/core/config.py`

## Findings
1. Scope multipliers and methodology description were hardcoded and not governance-driven (`CF-007`).
2. Extraction logic was heuristic-only and did not prioritize Carbon Footprint template paths (`CF-008`).
3. `ExternalPcfApi` references were not integrated into a controlled retrieval/provenance flow (`CF-009`).

## Implemented
- Introduced config-governed LCA multipliers, methodology, and disclosure fields.
- Updated extractor to support Carbon Footprint template-path-aware mappings and `ExternalPcfApi` reference extraction.
- Added controlled external PCF fetch path with feature flag, allowlist, timeout, and provenance logging.
- Added focused tests for extraction and external API integration behavior.

## Allowed Claims
- The platform computes and stores an internal PCF estimate based on configured factors and declared method metadata.
- The platform can ingest partner-provided PCF values through controlled external references.
- The platform does not claim third-party certified LCA or certificate substitution solely from the internal estimator.

## Evidence Command
```bash
uv run pytest tests/unit/test_lca_extractor.py tests/unit/test_lca_service_external_pcf.py -q
```

## Acceptance Criteria
- Reports include reproducible methodology metadata and disclosure text.
- Carbon Footprint template structures map predictably into `LCACalculation` report payloads.
- External PCF resolution is disabled by default unless configured, and logs fetch outcomes for auditability.
