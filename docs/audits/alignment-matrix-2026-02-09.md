# Alignment Matrix (2026-02-09)

Status values:
- `Aligned`
- `Partially Aligned`
- `Gap`

## DPP4.0 Template Coverage Matrix

| Requirement Area | Digital Nameplate | Carbon Footprint | Technical Data | Hierarchical Structures | Handover Documentation | Contact Information | Evidence Location |
|---|---|---|---|---|---|---|---|
| Template ingestion deterministic versioning | Partially Aligned | Partially Aligned | Partially Aligned | Partially Aligned | Partially Aligned | Partially Aligned | `backend/tests/unit/test_template_service.py`, findings `AUD-0001` |
| Parser fidelity (AAS semantics + qualifiers) | Partially Aligned | Partially Aligned | Partially Aligned | Partially Aligned | Partially Aligned | Partially Aligned | `backend/tests/unit/test_basyx_parser.py`, `backend/tests/unit/test_schema_from_definition.py` |
| Schema determinism and golden stability | Aligned | Aligned | Aligned | Aligned | Aligned | Aligned | `backend/tests/e2e/test_template_goldens.py` |
| Frontend renderer parity and validation UX | Partially Aligned | Partially Aligned | Partially Aligned | Partially Aligned | Partially Aligned | Partially Aligned | `frontend/src/features/editor/`, `frontend/src/features/publisher/pages/` |
| Revision provenance persistence | Aligned | Aligned | Aligned | Aligned | Aligned | Aligned | `backend/tests/unit/test_dpp_provenance_paths.py`, findings `AUD-0003` |
| Export conformance and semantic round-trip | Partially Aligned | Partially Aligned | Partially Aligned | Partially Aligned | Partially Aligned | Partially Aligned | `backend/tests/e2e/test_dpp_pipeline.py`, finding `AUD-0004` |
| Public viewer/tier access correctness | Aligned | Aligned | Aligned | Aligned | Aligned | Aligned | `backend/tests/unit/test_public_dpp_filtering.py`, `backend/tests/unit/test_public_dpp.py` |

## API/Contract Alignment Matrix

| Contract | Expected Behavior | Current Status | Evidence | Notes |
|---|---|---|---|---|
| `POST /api/v1/templates/refresh` | Returns attempted/successful/failed/skipped counters; `count` kept as deprecated alias | Aligned | `backend/tests/unit/test_templates_router_contract.py` | Additive change only |
| `GET /api/v1/templates` | Includes `support_status` and `refresh_enabled` metadata | Aligned | `backend/tests/unit/test_templates_router_contract.py` | Frontend selects only refreshable templates |
| DPP revision payload | `template_provenance` present for new revision paths | Aligned | `backend/tests/unit/test_dpp_provenance_paths.py` | Legacy rows may remain null |
