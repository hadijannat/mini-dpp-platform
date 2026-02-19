# OPC UA Phases 7–11: Backend Design

**Date**: 2026-02-19
**Status**: Approved
**Scope**: Phases 7–11 (all backend). Frontend (Phase 12) deferred.
**Prerequisite**: Phases 1–6 merged in PR #114 (config, models, migrations, OPA, CRUD, parser, transforms).

---

## Architecture Decision: Monolith-First Agent

The OPC UA agent runs as a **separate container with the same Docker image**, using a different entrypoint (`python -m app.opcua_agent`). This gives process isolation without code duplication — the agent imports shared models, encryption, transforms, and EPCIS capture directly.

```
OPC UA Server(s)
      │
      ▼
┌─────────────────────┐
│   opcua-agent        │  ← asyncua subscriptions, in-memory buffer
│   (port 8090 health) │
└─────────┬───────────┘
          │ direct DB writes via shared SQLAlchemy models
          ▼
┌─────────────────────┐     ┌─────────────────────┐
│   PostgreSQL         │◄───►│   FastAPI backend    │
│                      │     │   (port 8000)        │
└─────────────────────┘     └──────────┬──────────┘
                                       │
                            ┌──────────▼──────────┐
                            │   EDC / DTR          │
                            │   (dataspace)        │
                            └─────────────────────┘
```

**Safety rails preserved:**
- OPC UA connections never run inside uvicorn workers
- Agent crash does not take down the API
- Agent and API scale independently
- Feature-flagged: `opcua_enabled=false` → agent exits cleanly on startup

---

## Phase 7: OPC UA Agent (Worker Container)

### Package Layout

```
backend/app/opcua_agent/
  __init__.py
  __main__.py              # Entry: python -m app.opcua_agent
  connection_manager.py    # asyncua connection lifecycle per source
  subscription_handler.py  # Monitored items + data_change callbacks
  ingestion_buffer.py      # In-memory latest-value deduplication
  flush_engine.py          # Batched DPP patch commits via advisory locks
  epcis_emitter.py         # EPCIS event creation for mapping_type=EPCIS_EVENT
  deadletter.py            # Failed mapping recording
  health.py                # /healthz + /readyz + Prometheus metrics
```

### Lifecycle (`__main__.py`)

1. Parse config via `get_settings()` (shared with backend).
2. Create standalone `AsyncEngine` + `async_sessionmaker` (not the FastAPI-scoped session).
3. Start lightweight `aiohttp` health server on port 8090.
4. Enter main loop (runs forever):
   - **Poll phase** (every `opcua_agent_poll_interval_seconds`, default 5s): Query `opcua_mappings` joined with `opcua_sources` where `is_enabled=True`. Diff against currently subscribed items — add/remove subscriptions.
   - **Flush phase** (every `opcua_batch_commit_interval_seconds`, default 10s): Drain the ingestion buffer, apply coalesced patches.

### Connection Manager

- Maintains `dict[UUID, asyncua.Client]` keyed by `source_id`.
- Connect with `asyncio.wait_for(client.connect(), timeout=10)`.
- Exponential backoff with jitter on disconnect (1s → 2s → 4s → … max 60s).
- Updates `opcua_sources.connection_status` and `last_seen_at` on state transitions.
- Reads encrypted passwords via `ConnectorConfigEncryptor._decrypt_value()`.
- Downloads client certs from MinIO to temp dir when `auth_type=CERTIFICATE`.
- Respects `opcua_max_connections_per_tenant` limit.

### Subscription Handler

- Per source, creates one `asyncua.Subscription` per mapping group.
- Registers `MonitoredItemRequest` for each mapping's `opcua_node_id`.
- `datachange_notification` callback pushes `(mapping_id, value, server_timestamp, quality)` into ingestion buffer.
- Respects `opcua_max_subscriptions_per_source` and `opcua_max_monitored_items_per_subscription`.

### Ingestion Buffer

```python
# Key: (tenant_id, dpp_id, target_submodel_id, target_aas_path)
# Value: LatestValue(mapping_id, raw_value, transformed_value, server_ts, received_at)
_buffer: dict[tuple[UUID, UUID, str, str], LatestValue] = {}
```

- On each data change: overwrite entry (latest-value-wins deduplication).
- 100 OPC UA updates in 10s → 1 committed value per AAS path.
- Protected by `asyncio.Lock` (single event loop, guards flush vs callback).

### Flush Engine

Every `opcua_batch_commit_interval_seconds`:

1. Snapshot and clear buffer (swap under lock).
2. Group entries by `(tenant_id, dpp_id)`.
3. For each DPP:
   a. Acquire advisory lock: `pg_try_advisory_xact_lock(hashtext('opcua:flush:{dpp_id}'))`.
   b. If unavailable → re-queue entries for next window.
   c. Load latest DPP revision.
   d. Apply transforms via `apply_transform()` from `transform.py`.
   e. Build canonical patch operations grouped by `target_submodel_id`.
   f. Call `apply_canonical_patch()` to produce new AAS JSON.
   g. Create new `DPPRevision` row.
   h. Update `opcua_jobs.last_value_json` and `last_flush_at`.
   i. On failure → record in `opcua_deadletters` (increment count on repeats).

### Dead Letter Queue

- Failed patches recorded in `opcua_deadletters` with `count` incrementing on repeats.
- `opcua_deadletter_retention_days` (default 7) — agent periodically prunes old entries.
- Existing model and table from Phase 2; no new migration needed.

### Docker Compose

```yaml
opcua-agent:
  build:
    context: .
    dockerfile: backend/Dockerfile
    target: development
  container_name: dpp-opcua-agent
  command: python -m app.opcua_agent
  environment: *backend-env
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
  networks:
    - dpp-network
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "curl", "-fsS", "http://localhost:8090/healthz"]
    interval: 10s
    timeout: 5s
    retries: 3
    start_period: 30s
```

Same image, different entrypoint. No separate Dockerfile.

---

## Phase 8: GTIN / GS1 Digital Link Identity Binding

### AssetIdsInput Change

Add `gtin: str | None = None` to `AssetIdsInput` in `dpps/router.py`. Validated via `QRCodeService.validate_gtin()` on both create and update paths. Rejects with 422 if check digit is invalid.

### New Endpoint

```
GET /api/v1/t/{tenant_slug}/dpps/{dpp_id}/digital-link
```

Response:
```json
{
  "digitalLinkUri": "https://dpp-platform.dev/resolve/01/09506000134352/21/SN-2024-001",
  "gtin": "09506000134352",
  "serialNumber": "SN-2024-001",
  "isPseudoGtin": false,
  "resolverBaseUrl": "https://dpp-platform.dev/resolve"
}
```

Logic:
1. Explicit `gtin` in asset_ids → use it, `isPseudoGtin=false`.
2. No GTIN but `manufacturerPartId` → pseudo-GTIN, `isPseudoGtin=true`.
3. Build canonical URI: `{resolver_base_url}/01/{gtin}[/21/{serial}][/10/{batch}]`.
4. Requires `resolver_enabled=true` — otherwise 409.

### Auto-Registration on Publish

Existing `auto_register_resolver_links()` gains additional registration for GS1 Digital Link route using GTIN + serial/batch. Hooks into existing `asyncio.gather()` on publish — no new trigger.

### Files Modified

| File | Change |
|------|--------|
| `backend/app/modules/dpps/router.py` | Add `gtin` to `AssetIdsInput`, add `/digital-link` endpoint |
| `backend/app/modules/dpps/service.py` | `build_digital_link_uri()` helper |

~80 new lines.

---

## Phase 9: Dataspace Publication

### Service

**File: `backend/app/modules/opcua/dataspace.py`**

`DataspacePublicationService(session)`:
- `publish_to_dataspace(tenant_id, dpp_id, target, user_sub)` → DataspacePublicationJob
- `get_job(job_id, tenant_id)`, `list_jobs(...)`, `retry_job(job)`

### Publication Flow

1. Validate DPP is PUBLISHED.
2. Create job: `status=QUEUED` → transition to `RUNNING`.
3. **DTR registration**: Build shell descriptor using SAMM URN translations from `connectors/mapping.py`. Call `RegistryClient.register_shell()`. Store `dtr_shell_id` in `artifact_refs`.
4. **EDC asset creation**: Create asset, access policy (BPN-restricted or public), contract definition via `EDCManagementClient`. Store IDs in `artifact_refs`.
5. On success: `SUCCEEDED`. On failure: `FAILED` with error. Retryable.

### SAMM Mapping

Reuses 4 translations from `connectors/mapping.py` (Nameplate→SerialPart, CarbonFootprint→Pcf, etc.). If mapping has explicit `samm_aspect_urn`, uses it directly.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/dataspace/publish` | Trigger publication (`{dppId, target?}`) |
| `GET` | `/dataspace/jobs` | List jobs (filter by `dpp_id`) |
| `GET` | `/dataspace/jobs/{id}` | Job detail |
| `POST` | `/dataspace/jobs/{id}/retry` | Retry failed job |

### ABAC

New resource type `dataspace_publication_job`. Publisher/tenant_admin can trigger. Viewer can list/read.

### Files

| File | Change |
|------|--------|
| `backend/app/modules/opcua/dataspace.py` | New — publication service |
| `backend/app/modules/opcua/schemas.py` | 3 dataspace schemas |
| `backend/app/modules/opcua/router.py` | 4 endpoints |
| `infra/opa/policies/opcua_dataspace.rego` | ABAC policy |

~250 new lines.

---

## Phase 10: EPCIS Event Triggers

### Agent-Side Emitter

**File: `backend/app/opcua_agent/epcis_emitter.py`**

During buffer drain, entries with `mapping_type=EPCIS_EVENT` route here instead of flush engine:

1. Build `EPCISDocumentCreate` from mapping metadata (event_type, biz_step, disposition, action, read_point, biz_location).
2. Generate `sourceEventId` from template (`$value`, `$timestamp`, `$nodeId` placeholders) or default `{mapping_id}:{server_ts_iso}`.
3. Call `EPCISService.capture()` directly (shared code, not HTTP).

### Idempotency Guard

New migration `0042_epcis_source_event_id_uniqueness.py`:

```sql
CREATE UNIQUE INDEX uq_epcis_events_source_event_id
ON epcis_events (tenant_id, source_event_id)
WHERE source_event_id IS NOT NULL;
```

Partial index — existing events without `source_event_id` unaffected. Agent catches `IntegrityError` on duplicates, logs at DEBUG, skips.

### Trigger Semantics

Any value change (default). Coalescing still applies: 100 updates in 10s → 1 event with latest value. Rising-edge trigger deferred to future enhancement.

### Mapping Validation Extension

When `mapping_type=EPCIS_EVENT`:
- `epcis_event_type` required, must be one of 5 GS1 types.
- `epcis_action` required.
- `dpp_id` or `asset_id_query` must be set.
- Warning if `epcis_biz_step` empty.

### Files

| File | Change |
|------|--------|
| `backend/app/opcua_agent/epcis_emitter.py` | New — event construction + capture |
| `backend/app/opcua_agent/flush_engine.py` | Route EPCIS mappings to emitter |
| `backend/app/modules/opcua/service.py` | Extend validation for EPCIS rules |
| `backend/app/db/migrations/versions/0042_*.py` | Partial unique index |

~150 new lines.

---

## Phase 11: Observability & Secrets Hardening

### Health Endpoints

Lightweight `aiohttp` server on port 8090:

| Endpoint | Purpose |
|----------|---------|
| `GET /healthz` | Liveness — 200 if event loop responsive |
| `GET /readyz` | Readiness — 200 if DB pool alive + sources connected |
| `GET /metrics` | Prometheus text-format scrape |

### Prometheus Metrics

| Metric | Type | Labels |
|--------|------|--------|
| `opcua_agent_connections_active` | Gauge | tenant_id, source_id |
| `opcua_agent_subscriptions_active` | Gauge | tenant_id, source_id |
| `opcua_agent_buffer_entries` | Gauge | — |
| `opcua_agent_values_received_total` | Counter | tenant_id, source_id |
| `opcua_agent_flush_duration_seconds` | Histogram | — |
| `opcua_agent_flush_operations_total` | Counter | status |
| `opcua_agent_revisions_created_total` | Counter | tenant_id |
| `opcua_agent_epcis_events_emitted_total` | Counter | tenant_id |
| `opcua_agent_deadletters_total` | Counter | tenant_id |
| `opcua_agent_reconnects_total` | Counter | tenant_id, source_id |

### Secrets Handling

**Passwords**: Already encrypted via `ConnectorConfigEncryptor` (AES-256-GCM). No changes.

**Client certificates** (`auth_type=CERTIFICATE`):
- Stored in MinIO bucket `dpp-opcua-certs`.
- Path: `{tenant_id}/opcua_certs/{source_id}/client.pem` and `client.key`.
- Agent downloads to temp dir on connect, deletes after disconnect.
- Presigned upload URLs time-limited to 15 minutes, require `tenant_admin` role.

### Config Additions

```python
opcua_certs_bucket: str = "dpp-opcua-certs"
opcua_cert_presign_expiry_seconds: int = 900
```

### Cert Management Endpoints

| Method | Path | ABAC |
|--------|------|------|
| `POST` | `/sources/{id}/upload-cert-url` | tenant_admin |
| `POST` | `/sources/{id}/upload-key-url` | tenant_admin |
| `DELETE` | `/sources/{id}/certs` | tenant_admin |

### Production Compose

Add `opcua-agent` service to `docker-compose.prod.yml` under `*backend-env` anchor.

### Files

| File | Change |
|------|--------|
| `backend/app/opcua_agent/health.py` | New — aiohttp health + metrics |
| `backend/app/opcua_agent/*.py` | Metrics instrumentation |
| `backend/app/core/config.py` | 2 new settings |
| `backend/app/modules/opcua/router.py` | 3 cert endpoints |
| `backend/app/modules/opcua/service.py` | Cert presign URL generation |
| `docker-compose.yml` | Add opcua-agent service |
| `docker-compose.prod.yml` | Add opcua-agent service |
| `backend/pyproject.toml` | Add `prometheus_client` if needed |

~300 new lines.

---

## Full File Inventory

### New Files (13)

| # | File | Phase | Lines (est.) |
|---|------|-------|-------------|
| 1 | `backend/app/opcua_agent/__init__.py` | 7 | 1 |
| 2 | `backend/app/opcua_agent/__main__.py` | 7 | ~120 |
| 3 | `backend/app/opcua_agent/connection_manager.py` | 7 | ~180 |
| 4 | `backend/app/opcua_agent/subscription_handler.py` | 7 | ~120 |
| 5 | `backend/app/opcua_agent/ingestion_buffer.py` | 7 | ~80 |
| 6 | `backend/app/opcua_agent/flush_engine.py` | 7 | ~200 |
| 7 | `backend/app/opcua_agent/deadletter.py` | 7 | ~60 |
| 8 | `backend/app/opcua_agent/health.py` | 11 | ~120 |
| 9 | `backend/app/opcua_agent/epcis_emitter.py` | 10 | ~100 |
| 10 | `backend/app/modules/opcua/dataspace.py` | 9 | ~200 |
| 11 | `infra/opa/policies/opcua_dataspace.rego` | 9 | ~40 |
| 12 | `backend/app/db/migrations/versions/0042_epcis_source_event_id_uniqueness.py` | 10 | ~30 |
| 13 | `docs/plans/2026-02-19-opcua-phases-7-11-design.md` | — | this file |

### Modified Files (9)

| File | Phases | Changes |
|------|--------|---------|
| `backend/app/modules/dpps/router.py` | 8 | `gtin` field + `/digital-link` endpoint |
| `backend/app/modules/dpps/service.py` | 8 | `build_digital_link_uri()` helper |
| `backend/app/modules/opcua/router.py` | 9, 11 | 4 dataspace + 3 cert endpoints |
| `backend/app/modules/opcua/schemas.py` | 9 | 3 dataspace schemas |
| `backend/app/modules/opcua/service.py` | 10, 11 | EPCIS validation + cert presign |
| `backend/app/core/config.py` | 11 | 2 cert settings |
| `docker-compose.yml` | 7, 11 | opcua-agent service |
| `docker-compose.prod.yml` | 11 | opcua-agent service |
| `backend/pyproject.toml` | 11 | `prometheus_client` dep |

**Total: ~1,280 new lines across 13 new files + 9 modifications.**

---

## Reused Functions

| Function/Pattern | Location | Used By |
|------------------|----------|---------|
| `ConnectorConfigEncryptor._decrypt_value` | `core/encryption.py` | Connection manager |
| `apply_canonical_patch()` | `dpps/canonical_patch.py` | Flush engine |
| `apply_transform()` | `modules/opcua/transform.py` | Flush engine |
| `EPCISService.capture()` | `modules/epcis/service.py` | EPCIS emitter |
| `QRCodeService.validate_gtin()` | `modules/qr/service.py` | GTIN validation |
| `EDCManagementClient` | `connectors/edc/client.py` | Dataspace publication |
| `RegistryClient` | `connectors/registry/base.py` | Dataspace publication |
| `pg_try_advisory_xact_lock` | `dpps/router.py` pattern | Flush engine |
| `emit_audit_event()` | `core/audit.py` | All mutations |
| `trigger_webhooks()` | `webhooks/service.py` | All mutations |
| `require_access()` | `core/security/__init__.py` | All endpoints |
| SAMM URN translations | `connectors/mapping.py` | Dataspace publication |
