# CF-EX1 Template Versioning

## Owner
IDTA Template & Versioning Specialist

## Scope
- `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/catalog.py`
- `/Users/aeroshariati/mini-dpp-platform/backend/app/modules/templates/service.py`
- `/Users/aeroshariati/mini-dpp-platform/shared/idta_semantic_registry.json`

## Findings
1. Carbon footprint baseline and latest patch resolution are deterministic (`latest_patch` within `1.0`).
2. Source metadata capture (`source_file_path`, `source_file_sha`, `selection_strategy`) is preserved in template records.
3. Inspection bootstrap script was stale and unable to consume current service API (`CF-001`).

## Implemented
- Rewrote `/Users/aeroshariati/mini-dpp-platform/backend/tests/tools/inspection_setup.py` to use `TemplateRegistryService` + DB session lifecycle.

## Evidence Command
```bash
uv run pytest tests/unit/test_template_service.py -q
```

## Acceptance Criteria
- Script emits `definition.json`, `schema.json`, and source metadata per template.
- Summary output includes success/failed/skipped counters.
