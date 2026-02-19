# Mini DPP Platform

[![CI](https://github.com/hadijannat/mini-dpp-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/hadijannat/mini-dpp-platform/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](backend/pyproject.toml)
[![Node](https://img.shields.io/badge/node-20%2B-brightgreen)](frontend/package.json)

A multi-tenant Digital Product Passport (DPP) platform built on the Asset Administration Shell (AAS) and IDTA DPP4.0 standards. Integrates OPC UA industrial data, GS1 EPCIS 2.0 supply chain events, Catena-X dataspace connectivity, W3C Verifiable Credentials, and EU ESPR compliance — backed by FastAPI, React, Keycloak, OPA, PostgreSQL, Redis, and MinIO.

## What This Repository Is

A full-stack reference implementation for creating, editing, publishing, and sharing Digital Product Passports in a multi-tenant environment. Features include template-driven DPP authoring, AASX/JSON-LD/Turtle export, GS1 Digital Link resolution, OPC UA industrial data ingestion, EPCIS event capture, verifiable credential issuance, and ESPR compliance checking — with a production-oriented backend, React frontend, infrastructure manifests, CI/CD pipelines, and documentation set.

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
├── infra/                          # Keycloak, OPA, Helm, monitoring, ArgoCD, postgres init
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

## Capabilities by Module

| Area | Backend Modules | Frontend Features |
|------|----------------|-------------------|
| Tenant & Access | `tenants`, `policies`, `onboarding` | `admin`, `onboarding`, role-gated routes |
| DPP Lifecycle | `dpps`, `templates`, `masters` | `publisher`, `editor`, `dpp-outline` |
| Public Consumption | `dpps/public_router`, `registry/public_router`, `resolver/public_router`, `credentials/public_router` | `viewer`, `landing` |
| Exports & Carriers | `export`, `qr`, `data_carriers` | `publisher` (multi-select export, batch) |
| Compliance & Audit | `compliance`, `audit` | `compliance`, `audit` |
| Supply Chain Events | `epcis`, `digital_thread`, `lca` | `epcis` |
| OPC UA Integration | `opcua` (sources, nodesets, mappings, dataspace) | `opcua` (4-tab CRUD page) |
| Dataspace & Registry | `connectors`, `registry`, `resolver`, `credentials`, `dataspace` | `connectors`, admin pages |
| Sharing & Activity | `shares`, `activity` | `activity` |
| Regulatory | `cirpass`, `regulatory_timeline` | `cirpass-lab` |
| Submodel Browsing | `aas`, `templates` | `submodels` |
| Platform Settings | `settings`, `webhooks` | admin settings + webhooks pages |

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
| OPC UA | Industrial data source integration |
| ODRL | Dataspace policy language (Eclipse Dataspace Connector) |
| EU ESPR | Public viewer categorization and compliance checking |

## Where to Go Next

- Public docs index: [`docs/public/README.md`](docs/public/README.md)
- Getting started and walkthroughs: [`docs/public/getting-started/README.md`](docs/public/getting-started/README.md)
- Architecture reference: [`docs/public/architecture/README.md`](docs/public/architecture/README.md)
- Operations playbook: [`docs/public/operations/README.md`](docs/public/operations/README.md)
- Release process: [`docs/public/releases/release-guide.md`](docs/public/releases/release-guide.md)

## Contributing

1. Create a branch from `main`.
2. Run relevant checks locally (`backend` + `frontend` + docs quality).
3. Open a pull request with a concise summary, testing evidence, and screenshots for UI changes.
4. Note migrations and infra impacts explicitly.

## License

MIT. See [`LICENSE`](LICENSE).
