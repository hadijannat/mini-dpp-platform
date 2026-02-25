# Mini DPP Platform

[![CI](https://github.com/hadijannat/mini-dpp-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/hadijannat/mini-dpp-platform/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](backend/pyproject.toml)
[![Node](https://img.shields.io/badge/node-20%2B-brightgreen)](frontend/package.json)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18777192.svg)](https://doi.org/10.5281/zenodo.18777192)

A multi-tenant Digital Product Passport (DPP) platform built on the Asset Administration Shell (AAS) and IDTA DPP4.0 standards. Integrates OPC UA industrial data, GS1 EPCIS 2.0 supply chain events, Catena-X dataspace connectivity, W3C Verifiable Credentials, and EU ESPR compliance — backed by FastAPI, React, Keycloak, OPA, PostgreSQL, Redis, and MinIO.

## Live Deployment

- Main application: [https://dpp-platform.dev/](https://dpp-platform.dev/)
- Additional production URLs (API, docs, health, auth) are listed in [Service Endpoints](#service-endpoints).

## Citation & Archive (Zenodo)

This repository is archived on Zenodo for release `v0.1.0`, and the latest GitHub release is `v0.1.2`.

- DOI: [10.5281/zenodo.18777192](https://doi.org/10.5281/zenodo.18777192)
- Zenodo record: [https://zenodo.org/records/18777192](https://zenodo.org/records/18777192)
- Latest GitHub release: [v0.1.2](https://github.com/hadijannat/mini-dpp-platform/releases/tag/v0.1.2)
- Zenodo-linked GitHub release: [v0.1.0](https://github.com/hadijannat/mini-dpp-platform/releases/tag/v0.1.0)

If you use this software in research or reports, cite the Zenodo DOI above.

## What This Repository Is

A full-stack reference implementation for creating, editing, publishing, and sharing Digital Product Passports in a multi-tenant environment. Features include template-driven DPP authoring, AASX/JSON-LD/Turtle export, GS1 Digital Link resolution, OPC UA industrial data ingestion, EPCIS event capture, verifiable credential issuance, ESPR compliance checking, and a feature-flagged CEN draft compliance layer (prEN 18219/18220/18222) — with a production-oriented backend, React frontend, infrastructure manifests, CI/CD pipelines, and documentation set.

## Quick Start (Docker Compose)

### Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Available ports by default: `5173`, `8000`, `8080`, `5432`, `6379`, `8181`, `9000`, `9001`

### Start the stack

```bash
git clone https://github.com/hadijannat/mini-dpp-platform.git
cd mini-dpp-platform

cp .env.example .env
docker compose up -d
```

Migrations run automatically in the backend container startup command. To run them manually:

```bash
docker exec dpp-backend alembic upgrade head
```

Use `docker compose up -d --build` on first run or when Dockerfiles/dependencies change.

You can override ports via `.env` (for example `BACKEND_HOST_PORT`, `KEYCLOAK_HOST_PORT`).

### Default Test Users

| Username | Password | Role |
|----------|----------|------|
| publisher | publisher123 | Publisher |
| viewer | viewer123 | Viewer |
| admin | admin123 | Admin |

## Service Endpoints

| Service | Local | Production |
|---------|-------|------------|
| Frontend | http://localhost:5173 | https://dpp-platform.dev |
| Backend API | http://localhost:8000/api/v1/openapi.json | https://dpp-platform.dev/api/v1/openapi.json |
| API Docs (Swagger) | http://localhost:8000/api/v1/docs | https://dpp-platform.dev/api/v1/docs |
| Keycloak | http://localhost:8080 | https://auth.dpp-platform.dev |
| Health | http://localhost:8000/health | https://dpp-platform.dev/health |
| OPA | http://localhost:8181/health | — |
| MinIO API | http://localhost:9000 | — |
| MinIO Console | http://localhost:9001 | — |

## OPC UA Enablement Checklist

- Set `OPCUA_ENABLED=true` in your deployment environment (`.env`/`.env.prod` or shell env).
- Ensure both backend API and OPC UA agent are running:

```bash
docker compose -f docker-compose.prod.yml up -d backend opcua-agent
docker compose -f docker-compose.prod.yml ps backend opcua-agent
```

- Verify runtime flag inside the backend container:

```bash
docker compose -f docker-compose.prod.yml exec -T backend \
  python -c "from app.core.config import get_settings; print(get_settings().opcua_enabled)"
```

## Project Structure at a Glance

```text
mini-dpp-platform/
├── backend/                        # FastAPI app, modules, DB models/migrations, tests
├── frontend/                       # React + Vite app, feature modules, Playwright/Vitest tests
├── infra/                          # Keycloak, OPA, Helm, monitoring, ArgoCD, postgres init, sidecars
├── docs/
│   ├── public/                     # Public contributor/operator docs
│   └── internal/                   # Audits, evidence, planning, internal reviews
├── docker-compose.yml              # Default local development stack
├── docker-compose.prod.yml         # Production-oriented compose profile
├── docker-compose.edc.yml          # EDC overlay (Tractus-X connector sidecar)
├── docker-compose.dtr.yml          # Digital Twin Registry overlay
├── docker-compose.inspection.yml   # Isolated inspection stack (ports 5433/6380/8001/8081)
├── Caddyfile                       # Production reverse proxy config (HTTPS)
└── .github/workflows/              # CI, deploy, security, docs quality, pipeline workflows
```

## CEN prEN Profile Layer (18219/18220/18222)

This repository includes a versioned, feature-flagged CEN draft profile layer for:

- **prEN 18219**: identifier governance for canonical product/operator/facility identifiers
- **prEN 18220**: carrier preflight, renderer behavior (QR/DataMatrix/NFC), and QA checks
- **prEN 18222**: tenant/public CEN API facade with stable operation IDs and cursor-first search

Primary backend locations:

- `backend/app/standards/cen_pren/`
- `backend/app/modules/cen_api/`
- `backend/app/modules/identifiers/`
- `backend/app/modules/data_carriers/`

Key settings (backend):

- `CEN_DPP_ENABLED` (default off)
- `CEN_PROFILE_18219`
- `CEN_PROFILE_18220`
- `CEN_PROFILE_18222`
- `CEN_ALLOW_HTTP_IDENTIFIERS` (recommended `false` outside dev)

When enabled, CEN endpoints are mounted under:

- Tenant-scoped: `/api/v1/tenants/{tenant_slug}/cen`
- Public: `/api/v1/public/{tenant_slug}/cen`

Rollout/backfill guidance:

- Runbook: `docs/public/operations/cen-pren-rollout.md`
- Backfill tool: `backend/tools/backfill_cen_identifiers.py`

## Capabilities by Module

| Area | Backend Modules | Frontend Features |
|------|----------------|-------------------|
| Tenant & Access | `tenants`, `policies`, `onboarding` | `admin`, `onboarding`, role-gated routes |
| DPP Lifecycle | `dpps`, `templates`, `masters` | `publisher`, `editor`, `dpp-outline` |
| CEN Facade & Governance | `cen_api`, `identifiers`, `standards/cen_pren` | `publisher`, `admin` (targeted CEN actions) |
| Public Consumption | `dpps/public_router`, `registry/public_router`, `resolver/public_router`, `credentials/public_router` | `viewer`, `landing` |
| Exports & Carriers | `export`, `qr`, `data_carriers` | `publisher` (multi-select export, batch) |
| Compliance & Audit | `compliance`, `audit` | `compliance`, `audit` |
| Supply Chain Events | `epcis`, `digital_thread`, `lca` | `epcis` |
| RFID / TDS 2.3 | `rfid`, `tenant_domains`, `resolver`, `data_carriers` | `publisher` |
| OPC UA Integration | `opcua` (sources, nodesets, mappings, dataspace) | `opcua` (4-tab CRUD page) |
| Dataspace & Registry | `connectors`, `registry`, `resolver`, `credentials`, `dataspace` | `connectors`, admin pages |
| Sharing & Activity | `shares`, `activity` | `activity` |
| Regulatory | `cirpass`, `regulatory_timeline` | `cirpass-lab` |
| Submodel Browsing | `aas`, `templates` | `submodels` |
| Platform Settings | `settings`, `webhooks` | admin settings + webhooks pages |

## Measurement Units (IDTA-01003-b)

The backend implements IDTA-01003-b-compatible measurement unit handling with a BaSyx-safe runtime model:

- Template ingest stores two payloads:
  - `template_json`: sanitized payload used for strict BaSyx parsing.
  - `template_json_raw`: raw upstream payload retained for DataSpecificationUoM extraction.
- Template contract responses include additive UoM diagnostics (`uom_diagnostics`) and unit-resolution metadata.
- Validation is warn-only in this rollout (`UOM_VALIDATION_MODE=warn`); template refresh/export/import are not hard-blocked.
- Export paths enrich unit ConceptDescriptions in-memory (no revision mutation at write-time).
- Import paths strip DataSpecificationUoM for strict parser compatibility.

### Export guarantees

- Guaranteed UoM enrichment:
  - `json`
  - `jsonld`
  - `turtle`
  - `aasx` when `aasx_serialization=json`
- Best effort only:
  - `xml`
  - `aasx` when `aasx_serialization=xml`
  - these paths include warning header `X-UOM-Warning: uom_xml_not_guaranteed_due_basyx_limitation`

### Unit registry

- Initial canonical registry is UNECE Rec 20-backed.
- Registry data is persisted in `uom_units` and seeded from `backend/app/modules/units/data/uom.seed.json`.
- Runtime controls:
  - `UOM_REGISTRY_ENABLED`
  - `UOM_REGISTRY_SEED_PATH`
  - `UOM_ENRICHMENT_ENABLED`
  - `UOM_VALIDATION_MODE`

## Developer Workflows

### Backend (`backend/`)

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy app
uv run python tools/check_plaintext_connector_secrets.py
```

Backend test fixtures default to a PostgreSQL endpoint on `localhost:5433`. For a reproducible full run, start the inspection stack or set `TEST_DATABASE_URL` explicitly:

```bash
docker compose -f docker-compose.inspection.yml up -d
```

`tools/check_plaintext_connector_secrets.py` is a rollout guardrail that fails if legacy connector config fields or dataspace connector secret records contain plaintext values.

### Frontend (`frontend/`)

```bash
npm ci
npm run dev
npm run build
npm test -- --run
npm run test:e2e
npm run lint
npm run typecheck
npm run generate-api
```

`npm run generate-api` expects a running backend on `http://localhost:8000`.

## CI/CD Workflows

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| CI | `ci.yml` | Push/PR to `main`, `develop` | Lint, test, SAST, Docker build |
| Deploy | `deploy.yml` | Auto on CI success (main) or manual | GHCR images, Trivy scan, SSH deploy |
| DPP Pipeline | `dpp-pipeline.yml` | Push/PR to `main`, `develop` | Full Docker stack E2E + golden files |
| Dataspace Conformance | `dataspace-conformance.yml` | Daily cron + manual | Dataspace protocol conformance |
| Security | `security.yml` | Push/PR + manual | Security scanning (pip-audit, Trivy) |
| Docs Quality | `docs-quality.yml` | Push/PR to `main`, `develop` | Markdown lint + link validation |
| Regulatory Timeline | `regulatory-timeline-refresh.yml` | Daily cron + manual | Automated regulatory timeline refresh |

## Infrastructure

- **Helm chart**: `infra/helm/dpp-platform/` — Kubernetes deployment manifests
- **ArgoCD**: `infra/argocd/` — Multi-environment GitOps configuration
- **Monitoring**: Prometheus + Grafana (4 dashboards) + Alertmanager (`infra/monitoring/`)
- **Reverse proxy**: Caddy for production HTTPS termination and routing (`Caddyfile`)
- **Keycloak realm**: `infra/keycloak/realm-export/dpp-platform-realm.json`

## Web-Resolvable RFID (TDS 2.3 SGTIN++)

### Scope and architecture (current)

- v1 scope is **SGTIN++ only** (`tds_scheme=sgtin++`), with a staged translator design.
- Backend API contracts are stable and decoupled from translator implementation (`backend/app/modules/rfid`).
- Translation engine runs in a sidecar at `infra/rfid-tds` (`TagDataTranslation` + minimal .NET API).
- Configure sidecar connectivity with:
  - `RFID_TDS_SERVICE_URL` (default compose wiring: `http://rfid-tds:8080`)
  - `RFID_TDS_TIMEOUT_SECONDS` (default `5`)

### Tenant domains and authority model

- Tenant domain records are managed under:
  - `GET|POST /api/v1/tenants/{tenant_slug}/domains`
  - `PATCH|DELETE /api/v1/tenants/{tenant_slug}/domains/{domain_id}`
- Lifecycle (manual verification v1):
  - New domains are created as `pending`.
  - `pending` domains cannot be primary.
  - Only `active` domains can be marked `is_primary=true`.
  - Active domains must be disabled before deletion.
  - **Platform admin role is required** to activate a domain (`status=active`) or set `verification_method`.
- Hostnames are normalized/validated (lowercase DNS hostname, no scheme/path/port).

### Resolver behavior for branded Digital Link paths

- Public resolver is mounted both at:
  - Legacy path: `/api/v1/resolve/...` (backward compatible)
  - Root path: `/.well-known/gs1resolver`, `/01/...` (web-native Digital Link)
- Root-path resolution is **strictly host-authoritative**:
  - Request host must map to an `active` tenant domain.
  - Unmapped/disabled hosts return `404`.
- Content negotiation:
  - `Accept: application/linkset+json` -> RFC 9264 linkset response.
  - Other accepts (for example browsers) -> `307` redirect to prioritized resolver target.
- Resolver anchors and `resolverRoot` are built from external host/proto, with forwarded headers trusted only from configured `TRUSTED_PROXY_CIDRS`.
- Managed redirects preserve SSRF/open-redirect protections, while allowing same-host redirects.

### RFID APIs and EPCIS ingestion

- Tenant-scoped endpoints:
  - `POST /api/v1/tenants/{tenant_slug}/rfid/encode`
  - `POST /api/v1/tenants/{tenant_slug}/rfid/decode`
  - `POST /api/v1/tenants/{tenant_slug}/rfid/reads`
- `encode` behavior:
  - If hostname is omitted, backend uses tenant primary active domain.
  - Returns EPC payload (`epc_hex`), EPC URIs, and branded Digital Link URL.
- `reads` ingestion behavior:
  - Decodes each EPC read and attempts DPP match in this order:
    - `data_carriers.identifier_key` (`01/{gtin}/21/{serial}`)
    - fallback to DPP `asset_ids` (`gtin` + `serialNumber`) lookup
  - Creates EPCIS `ObjectEvent` with `action=OBSERVE` for matched reads.

### Data carrier support for RFID

- `data_carriers` now supports:
  - `carrier_type=rfid`
  - `identifier_scheme=gs1_epc_tds23`
- RFID key format is GS1 Digital Link-compatible: `01/{gtin}/21/{serial}`.
- RFID render outputs are programming-oriented:
  - `json` programming pack
  - `csv` one-row export for encoder pipelines

### Reliability and performance notes

- Sidecar client uses:
  - shared async HTTP client
  - bounded retries with short backoff for transient sidecar failures
- Read ingestion decodes in parallel with bounded concurrency to improve throughput on larger batches.

### Routing and operations notes

- Production Caddy routes `/.well-known/gs1resolver` and `/01/*` to backend for root-path resolution.
- If additional root AI paths are required (for example `/00/*`), add explicit Caddy `handle` rules.

### Licensing note

- `TagDataTranslation` is dual-licensed (AGPL/commercial). Confirm deployment license posture before production rollout.

## Cryptographic Security

### Integrity, authenticity, and non-repudiation

- **DPP revision integrity**: each revision stores `digest_sha256` plus a JWS signature (`signed_jws`) with `kid`.
- **Canonical hashing/signing**: new writes use RFC 8785 JSON canonicalization (`rfc8785`) with SHA-256.
- **Legacy compatibility**: verification supports historical `legacy-json-v1` rows where metadata indicates older canonicalization.
- **VC proof binding**: VC verification validates signature and proof-to-credential binding (`vc_hash`, `vc_hash_alg`, `vc_canon`) with constant-time compare, while keeping legacy proof compatibility.
- **Audit anchoring**: per-tenant audit events are hash-chained, periodically anchored as Merkle roots, signed with a dedicated audit key, and optionally RFC 3161 timestamped via `TSA_URL`.

### Public verification endpoints

- `GET /api/v1/public/{tenant_slug}/dpps/{dpp_id}/integrity`
  - Returns digest, signature, digest algorithm/canonicalization, signature `kid`, verification method URLs, and latest anchor reference.
- `GET /api/v1/public/.well-known/jwks.json`
  - Publishes verifier keys for signature validation.
- `GET /api/v1/public/{tenant_slug}/.well-known/did.json`
  - Publishes tenant DID documents for VC verification workflows.

### Confidentiality and key management

- **Field-level encryption**: AAS elements tagged `Confidentiality=encrypted` are encrypted before storage using AES-256-GCM.
- **Envelope encryption**: each encrypted revision uses a per-revision DEK wrapped by an active KEK (`wrapped_dek`, `kek_id`, `dek_wrapping_algorithm` metadata on revision).
- **Connector/dataspace secrets**: new writes use `enc:v2` tokens (key-id aware, AEAD); `enc:v1` remains readable for compatibility.
- **Key separation (required in staging/production)**: `AUDIT_SIGNING_KEY` must be different from `DPP_SIGNING_KEY`.

### Required crypto environment variables (staging/production)

- `DPP_SIGNING_KEY`, `DPP_SIGNING_KEY_ID`
- `AUDIT_SIGNING_KEY`, `AUDIT_SIGNING_KEY_ID`
- `ENCRYPTION_KEYRING_JSON` (preferred) or `ENCRYPTION_MASTER_KEY` (fallback), plus `ENCRYPTION_ACTIVE_KEY_ID`
- Optional: `TSA_URL` (for RFC 3161 timestamping of signed Merkle roots)

For scheduled anchoring, use `backend/tools/run_audit_anchoring.py` (or the Helm CronJob template `infra/helm/dpp-platform/templates/backend/audit-anchoring-cronjob.yaml`).

## Validation Snapshot (2026-02-19)

| Area | Command | Result |
|------|---------|--------|
| Backend lint | `uv run ruff check .` | Pass |
| Backend typecheck | `uv run mypy app` | Pass |
| Backend tests | `uv run pytest -q` (with inspection DB) | `1104 passed`, `34 skipped` |
| Frontend unit tests | `npm test -- --run` | `75 files`, `398 tests` — all pass |
| Frontend lint | `npm run lint` | Pass |
| Frontend typecheck | `npm run typecheck` | Pass |
| Frontend E2E | `npm run test:e2e` | Requires running stack (`docker compose up -d --build`) |
| Docs lint | `npx markdownlint-cli2 'README.md' 'CHANGELOG.md' 'docs/**/*.md'` | Pass |
| Link check | `lychee --config .lychee.toml README.md 'docs/**/*.md'` | Pass |

## Standards Alignment

| Standard / Spec | Role in This Repository |
|---|---|
| IDTA AAS (Part 1/2) | Core model structure for shells, submodels, and elements |
| IDTA AASX (Part 5) | AASX package export support |
| IDTA DPP4.0 templates | Dynamic template-driven DPP authoring and validation |
| Eclipse BaSyx Python SDK 2.0.0 | AAS object model and serialization/deserialization |
| GS1 Digital Link | Data carrier and resolver flows |
| GS1 EPCIS 2.0 | Supply chain event capture and query |
| W3C Verifiable Credentials 2.0 | DPP credential issuance (`did:web`, `JsonWebSignature2020`) |
| RFC 9264 Linkset | Resolver link format for GS1 Digital Link |
| IEC 61406 | Industrial identification for data carriers |
| CEN prEN 18219 (draft) | Canonical unique identifier governance and supersede flows |
| CEN prEN 18220 (draft) | Data-carrier validation/rendering/QA profile behaviors |
| CEN prEN 18222 (draft) | Tenant/public CEN API facade and lifecycle/search contracts |
| OPC UA | Industrial data source integration |
| ODRL | Dataspace policy language (Eclipse Dataspace Connector) |
| EU ESPR | Public viewer categorization and compliance checking |

## Where to Go Next

- Public docs index: [`docs/public/README.md`](docs/public/README.md)
- Getting started and walkthroughs: [`docs/public/getting-started/README.md`](docs/public/getting-started/README.md)
- Architecture reference: [`docs/public/architecture/README.md`](docs/public/architecture/README.md)
- Operations playbook: [`docs/public/operations/README.md`](docs/public/operations/README.md)
- CEN rollout guide: [`docs/public/operations/cen-pren-rollout.md`](docs/public/operations/cen-pren-rollout.md)
- Release process: [`docs/public/releases/release-guide.md`](docs/public/releases/release-guide.md)

## Contributing

1. Create a branch from `main`.
2. Run relevant checks locally (`backend` + `frontend` + docs quality).
3. Open a pull request with a concise summary, testing evidence, and screenshots for UI changes.
4. Note migrations and infra impacts explicitly.

## License

MIT. See [`LICENSE`](LICENSE).
