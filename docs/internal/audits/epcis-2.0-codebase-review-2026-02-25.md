# EPCIS 2.0 Codebase Review (2026-02-25)

## Scope
- Repository: `hadijannat/mini-dpp-platform`
- Focus: EPCIS 2.0 capture/query/public-read paths, GS1 validation, DB model/migrations, related integrations (OPC UA, export/AAS bridge, resolver), and test coverage.
- Excluded: non-EPCIS business logic, non-EPCIS UI routes.

## Endpoint Inventory

### Tenant-authenticated EPCIS endpoints
- `POST /api/v1/tenants/{tenant_slug}/epcis/capture`
  - Router: `backend/app/modules/epcis/router.py`
  - Behavior: Persist EPCIS 2.0 document events for a DPP (`dpp_id` query param).
- `GET /api/v1/tenants/{tenant_slug}/epcis/events`
  - Router: `backend/app/modules/epcis/router.py`
  - Behavior: SimpleEventQuery-style filtering.
- `GET /api/v1/tenants/{tenant_slug}/epcis/events/{event_id}`
  - Router: `backend/app/modules/epcis/router.py`
  - Behavior: fetch single event.
- `POST /api/v1/tenants/{tenant_slug}/epcis/queries`
- `GET /api/v1/tenants/{tenant_slug}/epcis/queries`
- `GET /api/v1/tenants/{tenant_slug}/epcis/queries/{name}/events`
- `DELETE /api/v1/tenants/{tenant_slug}/epcis/queries/{name}`

### Public EPCIS endpoint
- `GET /api/v1/public/{tenant_slug}/epcis/events/{dpp_id}`
  - Router: `backend/app/modules/epcis/public_router.py`
  - Contract: only published DPPs; no auth required.
  - Current behavior (after this PR): select most-recent 100 by `event_time DESC`, return chronological order in response.

## Schema Coverage
- Event union in `backend/app/modules/epcis/schemas.py`:
  - `ObjectEvent`, `AggregationEvent`, `TransactionEvent`, `TransformationEvent`, `AssociationEvent`
- Document wrapper:
  - `EPCISDocumentCreate` with `@context`, `schemaVersion`, `creationDate`, `epcisBody.eventList`
- Query params schema:
  - Event type/time/action/bizStep/disposition/epc matching/read point/location/record time + pagination
- Public response schema:
  - `PublicEPCISEventResponse` excludes `created_by_subject` and `created_at`

## DB Tables and Indexes
- Table: `epcis_events`
  - Model: `backend/app/db/models.py` (`EPCISEvent`)
  - Migration: `backend/app/db/migrations/versions/0016_epcis_events.py`
  - Key indexes:
    - `ix_epcis_events_tenant_dpp_time`
    - `ix_epcis_events_event_id` (unique)
    - `ix_epcis_events_biz_step`
    - `ix_epcis_events_payload` (GIN)
- Table: `epcis_named_queries`
  - Model: `backend/app/db/models.py` (`EPCISNamedQuery`)
  - Migration: `backend/app/db/migrations/versions/0017_epcis_named_queries.py`
  - Constraint: tenant-scoped unique `(tenant_id, name)`

## Feature Flags / Settings
- `epcis_enabled`
- `epcis_auto_record`
- `epcis_validate_gs1_schema`
- Source: `backend/app/core/config.py`

## Integration Touchpoints
- DPP lifecycle auto-events:
  - `backend/app/modules/epcis/handlers.py`
  - Called from `backend/app/modules/dpps/router.py`
- Export / AAS traceability injection:
  - `backend/app/modules/epcis/aas_bridge.py`
  - Wired from `backend/app/modules/export/router.py` and `backend/app/modules/export/service.py`
- OPC UA event emission:
  - `backend/app/opcua_agent/epcis_emitter.py`
  - Validated by `backend/tests/test_opcua_epcis_emitter.py`
- GS1 Digital Link helper:
  - `backend/app/modules/epcis/digital_link.py`

## Test Coverage Inventory
- Backend unit tests:
  - `backend/tests/unit/test_epcis_schemas.py`
  - `backend/tests/unit/test_epcis_gs1_validator.py`
  - `backend/tests/unit/test_epcis_digital_link.py`
  - `backend/tests/unit/test_epcis_named_queries.py`
  - `backend/tests/unit/test_epcis_public.py`
  - `backend/tests/unit/test_epcis_error_correction.py`
  - `backend/tests/unit/test_epcis_handlers.py`
  - `backend/tests/unit/test_epcis_cbv.py`
- Backend e2e:
  - `backend/tests/e2e/test_epcis_flow.py`
- OPC UA EPCIS path:
  - `backend/tests/test_opcua_epcis_emitter.py`
- Frontend EPCIS tests:
  - `frontend/src/features/epcis/__tests__/CaptureDialog.test.tsx`
  - `frontend/src/features/epcis/__tests__/EventFilters.test.tsx`
  - `frontend/src/features/epcis/__tests__/EPCISTimeline.test.tsx`

## Risks / Findings
1. GS1 warning handling was previously over-strict.
- `validate_against_gs1_schema()` emits warning-tagged messages (`(warning)`), but service treated all messages as blocking.
- Impact: valid captures could fail due to warning-level findings.

2. Public endpoint recency selection mismatch.
- Public router previously selected oldest rows due to ascending order with limit.
- Impact: endpoint could omit most recent events despite claiming "most recent" window.

3. Test harness warning noise in lifecycle handler tests.
- AsyncMock-based `session.add` caused un-awaited coroutine warnings.
- Impact: noisy signals that can mask real warnings/regressions.

4. Public policy wording conflict.
- Public data policy stated raw EPCIS payload/location data are prohibited everywhere, while dedicated public EPCIS endpoint contract includes those fields for published DPP traceability.
- Impact: documentation and implementation contradiction.

## Improvements Implemented in This PR
- GS1 validation split into structural errors (blocking) vs warning-tagged findings (logged, non-blocking).
- Public EPCIS endpoint now selects latest event window and returns chronologically.
- Handler test fixture updated to use sync `add` mock (warning-free).
- Public policy clarified with explicit published-DPP EPCIS endpoint carve-out.
- Added/updated tests for GS1 warning handling and public endpoint recency semantics.
