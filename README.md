# Mini DPP Platform

[![CI](https://github.com/hadijannat/mini-dpp-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/hadijannat/mini-dpp-platform/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](backend/pyproject.toml)
[![Node](https://img.shields.io/badge/node-20%2B-brightgreen)](frontend/package.json)

A contributor-focused Digital Product Passport (DPP) platform built on Asset Administration Shell (AAS) and IDTA DPP4.0 templates, with FastAPI, React, Keycloak, OPA, PostgreSQL, Redis, and MinIO.

## What This Repository Is

This repository contains a full-stack reference implementation for creating, editing, publishing, and sharing Digital Product Passports in a multi-tenant environment. It includes a production-oriented backend and frontend, infra manifests, CI/CD workflows, and an expanding public/internal documentation set.

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

## Service Endpoints

| Service | URL (default) | Notes |
|---|---|---|
| Frontend | http://localhost:5173 | Publisher/admin console and public landing page |
| API Docs | http://localhost:8000/api/v1/docs | Swagger UI served by custom docs endpoint |
| API OpenAPI | http://localhost:8000/api/v1/openapi.json | Contract source for client generation |
| API Health | http://localhost:8000/health | Returns `healthy` or `degraded` with dependency checks |
| Keycloak | http://localhost:8080 | Realm `dpp-platform`; admin console at `/admin` |
| OPA | http://localhost:8181/health | Policy engine health endpoint |
| MinIO API | http://localhost:9000 | S3-compatible object storage |
| MinIO Console | http://localhost:9001 | Local object storage console |

## Project Structure at a Glance

```text
mini-dpp-platform/
├── backend/                  # FastAPI app, modules, DB models/migrations, tests
├── frontend/                 # React + Vite app, feature modules, Playwright/Vitest tests
├── infra/                    # Keycloak, OPA, Helm, monitoring, ArgoCD, postgres init
├── docs/
│   ├── public/               # Public contributor/operator docs
│   └── internal/             # Audits, evidence, planning, internal reviews
├── docker-compose.yml        # Default local development stack
├── docker-compose.prod.yml   # Production-oriented compose profile
└── .github/workflows/        # CI, security, docs quality, deploy workflows
```

## Capabilities by Module

| Area | Key Backend Modules | Key Frontend Features |
|---|---|---|
| Tenant & Access | `tenants`, `policies`, `shares`, `onboarding` | `admin`, `onboarding`, role-gated routes |
| DPP Lifecycle | `dpps`, `masters`, `templates` | `publisher`, `editor` |
| Public Consumption | `dpps/public_router`, `registry/public_router`, `resolver/public_router` | `viewer` |
| Exports & Carriers | `export`, `qr` | `publisher/DataCarriersPage` |
| Compliance & Audit | `compliance`, `audit`, `activity` | `compliance`, `audit`, `activity` |
| Supply Chain Events | `epcis`, `digital_thread`, `lca` | `epcis`, dashboard EPCIS widgets |
| Dataspace/Registry Integrations | `connectors`, `registry`, `resolver`, `credentials` | `connectors`, admin registry/resolver/credentials pages |
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

Backend test fixtures default to a PostgreSQL endpoint on `localhost:5433`. For a reproducible full run, start `docker-compose.inspection.yml` or set `TEST_DATABASE_URL` explicitly (see Validation Snapshot).

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

## Validation Snapshot (2026-02-10)

| Area | Command | Result |
|---|---|---|
| Backend lint | `uv run ruff check .` (in `backend/`) | Pass |
| Backend typecheck | `uv run mypy app` (in `backend/`) | Pass |
| Backend tests (default env) | `uv run pytest -q` (in `backend/`) | Fails integration setup (test fixture expects `localhost:5433` test DB credentials) |
| Backend tests (aligned env) | `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/dpp_inspection uv run pytest -q` | Pass (`1104 passed`, `34 skipped`) |
| Frontend unit tests | `npm test -- --run` (in `frontend/`) | Pass (`28 files`, `263 tests`) |
| Frontend lint | `npm run lint` (in `frontend/`) | Pass with 2 warnings |
| Frontend typecheck | `npm run typecheck` (in `frontend/`) | Pass |
| Frontend E2E | `npm run test:e2e` (in `frontend/`) | Fail (`15/15` timeout waiting for `templates-refresh-all`; Vite overlay import error: `sonner`) |
| Docs lint | `npx markdownlint-cli2 'README.md' 'CHANGELOG.md' 'docs/**/*.md'` | Pass |
| Link check | `lychee --config .lychee.toml README.md 'docs/**/*.md'` | Pass |

## Known E2E Caveat

The current Playwright E2E failures are not random: all failing scenarios time out while waiting for `data-testid="templates-refresh-all"`, and failure traces show the Vite overlay error:

`[plugin:vite:import-analysis] Failed to resolve import "sonner" from "src/main.tsx"`

Observed precondition: running E2E against a frontend container/runtime with stale dependencies after lockfile changes. Before rerunning E2E, rebuild/reinstall frontend dependencies in the active runtime:

```bash
docker compose build frontend
docker compose up -d frontend
docker compose exec frontend npm ci
```

Failure traces and screenshots are stored under `frontend/test-results/`.

## Standards Alignment

| Standard / Spec | Role in This Repository |
|---|---|
| IDTA AAS (Part 1/2) | Core model structure for shells, submodels, and elements |
| IDTA AASX (Part 5) | AASX package export support |
| IDTA DPP4.0 templates | Dynamic template-driven DPP authoring and validation |
| Eclipse BaSyx Python SDK 2.0.0 | AAS object model and serialization/deserialization |
| GS1 Digital Link | Data carrier and resolver flows |
| EU ESPR context | Public viewer categorization and disclosure framing |

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
