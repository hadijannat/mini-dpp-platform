# Operations

This playbook focuses on runtime operations, compose/deployment variants, environment contracts, checks, and troubleshooting.

## Compose and Deployment Variants

| File | Purpose | Typical Command |
|---|---|---|
| `docker-compose.yml` | Default local development stack | `docker compose up -d` |
| `docker-compose.prod.yml` | Production-oriented stack with Caddy, monitoring, backup, migrate profile | `docker compose -f docker-compose.prod.yml up -d` |
| `docker-compose.inspection.yml` | Inspection/audit-oriented local environment | `docker compose -f docker-compose.inspection.yml up -d` |
| `docker-compose.edc.yml` | Adds EDC controlplane/dataplane + vault + EDC DB | `docker compose -f docker-compose.yml -f docker-compose.edc.yml up -d` |
| `docker-compose.dtr.yml` | Adds DTR service for Catena-X style registry flow | `docker compose -f docker-compose.yml -f docker-compose.dtr.yml up -d` |

Use `--build` when Dockerfiles or dependency layers changed, not on every startup.

## Migration Behavior

### Development (`docker-compose.yml`)

Backend startup command runs migrations automatically before launching Uvicorn.

Manual rerun:

```bash
docker exec dpp-backend alembic upgrade head
```

### Production (`docker-compose.prod.yml`)

Use the one-off migration service before/with rollout:

```bash
docker compose -f docker-compose.prod.yml --profile migrate run --rm migrate
```

The deploy workflow also executes migration and rolls back on failure.

## Environment Variable Contract

### Development (`.env.example`)

Core knobs:

- Keycloak admin bootstrap (`KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD`)
- Optional host-port overrides (`KEYCLOAK_HOST_PORT`, `BACKEND_HOST_PORT`)
- Optional allowed client IDs (`KEYCLOAK_ALLOWED_CLIENT_IDS`)
- Optional template GitHub token (`IDTA_TEMPLATES_GITHUB_TOKEN`)
- Optional asset ID base URI default (`GLOBAL_ASSET_ID_BASE_URI_DEFAULT`)

### Production (`.env.prod.example`)

Critical categories:

- PostgreSQL/Redis credentials
- Keycloak admin + Keycloak DB + backend client secret
- SMTP settings (Keycloak verification + backend notifications)
- Onboarding verification UX settings (`ONBOARDING_VERIFICATION_*`)
- MinIO credentials
- `ENCRYPTION_MASTER_KEY` and signing keys
- Optional template pin/ref settings

## Keycloak Realm Reconciliation (Production)

`--import-realm` does not overwrite an existing realm. Use an explicit post-deploy reconciliation step.

### Run reconciliation in the running Keycloak container

```bash
docker compose -f docker-compose.prod.yml exec keycloak \
  /opt/keycloak/bin/reconcile-prod-realm.sh
```

The script enforces:

- `registrationAllowed=true`
- `verifyEmail=true`
- `realm-management` roles on `service-account-dpp-backend`:
  - `manage-users`
  - `view-users`
  - `query-users`
  - `view-realm`

### Explicit live realm check command

```bash
docker compose -f docker-compose.prod.yml exec keycloak \
  /opt/keycloak/bin/kcadm.sh get realms/dpp-platform \
  --fields realm,registrationAllowed,verifyEmail,smtpServer
```

## Auth Onboarding Smoke Test

Run this after IAM or email-related changes:

1. Register a brand-new user via hosted Keycloak registration.
2. Confirm verification email arrives (inbox + spam/junk).
3. Complete email verification from the verification link.
4. Sign in and complete onboarding (`/welcome`) to provision viewer membership.
5. Submit a `publisher` role request from the welcome flow.
6. Review and approve request using a `tenant_admin` account in `/console/role-requests`.
7. Refresh token/sign in again as requester and confirm publisher access.

## Health, Metrics, and Runtime Checks

| Check | Endpoint / Command | Notes |
|---|---|---|
| Backend health | `GET http://localhost:8000/health` | Includes DB/Redis and optional EDC check summary |
| API docs | `GET http://localhost:8000/api/v1/docs` | Swagger UI |
| Prometheus metrics | `GET /metrics` | Dev: open when token unset. Production: token-gated or hidden |
| OPA health | `GET http://localhost:8181/health` | OPA runtime status |
| Compose service status | `docker compose ps` | Container-level readiness snapshot |
| Logs | `docker compose logs -f backend frontend keycloak` | Primary triage stream |

## CI/CD and Quality Gates

| Workflow | File | Gate Focus |
|---|---|---|
| CI | `.github/workflows/ci.yml` | Backend/frontend lint/tests/security, AAS validation, Helm lint/template, image build |
| DPP Pipeline | `.github/workflows/dpp-pipeline.yml` | End-to-end refresh/build/export/compliance path |
| Security | `.github/workflows/security.yml` | SBOM generation + Trivy filesystem scan |
| Docs Quality | `.github/workflows/docs-quality.yml` | Markdown lint + link validation |
| Deploy | `.github/workflows/deploy.yml` | Build/push images, scans, package Helm chart, SSH deploy + health verify |

## Repeatable Operational Tasks

### Refresh templates

```bash
TOKEN=$(curl -s -X POST "http://localhost:8080/realms/dpp-platform/protocol/openid-connect/token" \
  -d "client_id=dpp-backend" \
  -d "client_secret=backend-secret-dev" \
  -d "username=publisher" \
  -d "password=publisher123" \
  -d "grant_type=password" | jq -r '.access_token')

curl -X POST "http://localhost:8000/api/v1/templates/refresh" \
  -H "Authorization: Bearer $TOKEN"
```

### Run docs quality checks

```bash
npx markdownlint-cli2 'README.md' 'CHANGELOG.md' 'docs/**/*.md'
lychee --config .lychee.toml README.md 'docs/**/*.md'
```

### Backend verification with explicit test DB URL

```bash
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/dpp_inspection \
  uv run pytest -q
```

## Troubleshooting Matrix

| Symptom | Likely Cause | Resolution |
|---|---|---|
| Integration tests fail at DB setup (`localhost:5433`) | Test fixture expects DB endpoint/credentials not currently provisioned | Start inspection Postgres or set `TEST_DATABASE_URL` explicitly to a valid database |
| Playwright E2E times out at `templates-refresh-all` with Vite overlay import error (`sonner`) | Frontend runtime has stale/invalid `node_modules` for current lockfile | Rebuild/restart frontend runtime and reinstall deps (`docker compose build frontend && docker compose up -d frontend && docker compose exec frontend npm ci`) |
| Templates not loading and DB errors appear | Migrations missing or failed | Run `docker exec dpp-backend alembic upgrade head` |
| Keycloak changes from realm export not reflected in existing prod realm | Realm import only applies on first creation | Apply realm changes via `kcadm.sh` or admin UI on existing realm |
| Verification emails not delivered | SMTP misconfiguration or sender domain not trusted | Validate `KEYCLOAK_SMTP_*`, then run live realm check command and test with a real mailbox |
| Resend verification always fails with `429` | Cooldown window still active | Respect `Retry-After` header and wait until `next_allowed_at` before retrying |
| Role approval succeeds in DB but Keycloak role does not sync | Missing backend service-account permissions in Keycloak | Run reconciliation script and verify `realm-management` roles for `service-account-dpp-backend` |
| Port binding conflicts | Local machine already using default ports | Override host ports in `.env` and restart stack |

## Related Docs

- Getting started: [`../getting-started/README.md`](../getting-started/README.md)
- Architecture: [`../architecture/README.md`](../architecture/README.md)
- Release guide: [`../releases/release-guide.md`](../releases/release-guide.md)
- Public data policy: [`public-data-exposure-policy.md`](public-data-exposure-policy.md)
