# Platform & DevOps Review -- Phase 1 Findings Report

**Reviewer:** platform-devops
**Date:** 2026-02-06
**Scope:** Infrastructure, CI/CD, container security, database HA, observability, backup/DR

---

## Top 10 Findings (Ranked by Severity)

---

### Finding 1: No Automated PostgreSQL Backup or Point-in-Time Recovery (P0 -- Critical)

**Description:**
There is no automated backup mechanism for the PostgreSQL database. The production `docker-compose.prod.yml` mounts a named Docker volume (`postgres_data`) but there is no scheduled `pg_dump`, no WAL archiving, no external backup service (e.g., pgBackRest, Barman), and no offsite storage. A volume loss, accidental `DROP TABLE`, or host failure results in **complete, irrecoverable data loss** of all DPPs, tenants, audit events, and policies.

**Evidence:**
- `docker-compose.prod.yml:39` -- `postgres_data:/var/lib/postgresql/data` (Docker volume only)
- No `pg_dump` cron, no WAL archiving config, no backup script anywhere in the repository
- `grep -ri backup` returns zero infrastructure-related results

**Risk:** Total data loss. RPO = infinity (no recovery point). For a regulatory DPP platform holding EU ESPR compliance data, this is unacceptable.

**Fix Plan:**
1. Add a `backup` sidecar container running `prodrigestivill/postgres-backup-local` (or equivalent) with daily `pg_dump` to a mounted host directory
2. Configure WAL archiving (`archive_mode = on`) to a local or S3-compatible target (MinIO is already deployed)
3. Add a nightly cron job that ships backups offsite (e.g., to a second Hetzner Storage Box or S3)
4. Document and test the restore procedure in a runbook

**Acceptance Criteria:**
- Automated daily full backup with 7-day retention on host filesystem
- WAL archiving enabled for PITR with < 5 min RPO
- Offsite copy of latest backup
- Tested restore procedure documented in `docs/runbook/backup-restore.md`

**Test Plan:**
- Verify backup cron runs and produces valid dump files (`pg_restore --list`)
- Simulate data loss: drop a table, restore from backup, verify data integrity
- Verify WAL replay to a specific timestamp

**Effort:** 1-2 days

---

### Finding 2: Deploy Causes Downtime -- No Zero-Downtime Strategy (P0 -- Critical)

**Description:**
The deploy workflow (`deploy.yml:76-78`) runs `docker compose up -d --build` which tears down and rebuilds all containers including the backend. Combined with the backend startup command (`docker-compose.prod.yml:177-179`) which runs `alembic upgrade head` synchronously before starting uvicorn, every deploy causes a full service outage. There is no rolling restart, blue-green, or canary mechanism.

Additionally, with 4 uvicorn workers (`--workers 4`), the Alembic migration runs in the main process before forking, but if the migration is long-running, the health check will fail and dependent services may restart.

**Evidence:**
- `deploy.yml:76-78` -- `git pull origin main && docker compose -f docker-compose.prod.yml up -d --build`
- `docker-compose.prod.yml:177-179` -- `sh -c "python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4"`
- No health check on backend container in `docker-compose.prod.yml` (Caddy depends on `service_started`, not `service_healthy`)
- No rollback mechanism in the deploy script

**Risk:** Every production deploy causes user-visible downtime. Long-running migrations extend the outage window. Failed migrations leave the system in a partially broken state with no automated rollback.

**Fix Plan:**
1. Separate migration step: run `alembic upgrade head` as a one-off `docker compose run` before restarting the backend service
2. Add a healthcheck to the backend container in `docker-compose.prod.yml` (like dev compose has via depends_on)
3. Implement deploy script with ordered restart: migrate -> restart backend (one container at a time if possible) -> restart frontend
4. Add a rollback step that checks backend health after deploy and reverts `git checkout` + `docker compose up -d` on failure
5. Long-term: move to a container orchestrator (Docker Swarm or K8s) for true rolling updates

**Acceptance Criteria:**
- Deploy script separates migration from application restart
- Backend has a healthcheck in prod compose
- Deploy script includes health verification and automatic rollback on failure
- Deploy runbook documented

**Test Plan:**
- Time a deploy and verify no 502/503 responses during the window (use `curl` loop)
- Simulate a failed migration (bad revision), verify rollback triggers
- Verify health check endpoint responds correctly

**Effort:** 1-2 days

---

### Finding 3: No Observability Stack -- No Metrics, Tracing, or Alerting (P1 -- High)

**Description:**
The platform has structured JSON logging only (via `app.core.logging`). There is no Prometheus metrics endpoint, no OpenTelemetry instrumentation, no distributed tracing, and no alerting system. The health check endpoint (`/health`) returns a static `{"status": "healthy"}` without checking database or Redis connectivity. In production, there is no way to know if the system is degraded until users report issues.

**Evidence:**
- `backend/app/main.py:108-110` -- Health check is a static response, does not probe dependencies
- `grep -ri prometheus` across `backend/` returns zero results
- `grep -ri opentelemetry` across `backend/` returns zero results
- No Grafana, Prometheus, or Alertmanager containers in any compose file
- Keycloak has `KC_METRICS_ENABLED: true` (dev compose only, line 65) but nothing consumes these metrics

**Risk:** Silent failures. Database connection pool exhaustion, Redis evictions, OPA timeouts, and slow queries go undetected. No capacity planning data. Incident response is reactive and blind.

**Fix Plan:**
1. Add `prometheus-fastapi-instrumentator` to the backend for automatic request metrics
2. Enhance `/health` to a deep health check that probes Postgres, Redis, OPA, and MinIO
3. Add a Prometheus + Grafana stack to `docker-compose.prod.yml` (or use a hosted solution)
4. Add alerting rules: error rate > 1%, p99 latency > 2s, DB pool saturation > 80%, Redis memory > 90%
5. Instrument critical paths (DPP publish, export, Catena-X sync) with OpenTelemetry spans

**Acceptance Criteria:**
- `/health` returns dependency status (db, redis, opa)
- Prometheus scrapes backend metrics at `/metrics`
- Grafana dashboard shows request rate, latency, error rate, DB pool usage
- At least 3 alerting rules configured and tested

**Test Plan:**
- Verify `/metrics` endpoint returns Prometheus format data
- Stop Redis, verify `/health` reports degraded status
- Trigger alert by killing OPA, verify notification fires
- Load test and observe metrics in Grafana

**Effort:** 2-3 days

---

### Finding 4: No Container Resource Limits in Production (P1 -- High)

**Description:**
No service in `docker-compose.prod.yml` has memory or CPU limits set. A single misbehaving container (e.g., a memory leak in the backend, Keycloak under load, or a runaway query in Postgres) can consume all host resources and cause cascading failures across all services. The Hetzner VPS is a single server with finite RAM.

**Evidence:**
- `docker-compose.prod.yml` -- `grep -c 'mem_limit\|cpus\|deploy:\|resources:' = 0` (no resource constraints anywhere)
- Redis is self-limited to 256MB (`maxmemory 256mb`) but no container-level limit
- PostgreSQL has no `shared_buffers`, `work_mem`, or `max_connections` tuning

**Risk:** OOM killer can terminate critical containers (Postgres) if another service exhausts memory. No isolation between services on a single host.

**Fix Plan:**
1. Add `deploy.resources.limits` to each service in `docker-compose.prod.yml`:
   - postgres: 1GB RAM, 1 CPU
   - redis: 300MB RAM, 0.5 CPU
   - backend: 1GB RAM, 2 CPUs
   - frontend (nginx): 128MB RAM, 0.25 CPU
   - keycloak: 1GB RAM, 1 CPU
   - opa: 256MB RAM, 0.25 CPU
   - minio: 512MB RAM, 0.5 CPU
   - caddy: 128MB RAM, 0.25 CPU
2. Tune PostgreSQL: `shared_buffers=256MB`, `work_mem=4MB`, `max_connections=100`
3. Add `--oom-score-adj` to ensure Postgres is the last to be killed

**Acceptance Criteria:**
- Every service in prod compose has memory limit and CPU limit
- PostgreSQL has tuned `shared_buffers` and `max_connections`
- System survives a simulated OOM condition on a non-critical service without losing Postgres

**Test Plan:**
- Deploy with limits, run `docker stats` to verify enforcement
- Stress-test backend with concurrent requests, verify it hits the limit gracefully (503) rather than crashing Postgres
- Simulate memory pressure, verify OOM kills the right container

**Effort:** 0.5 day

---

### Finding 5: Single Redis Instance -- Shared Rate Limiter + Cache with LRU Eviction (P1 -- High)

**Description:**
A single Redis instance serves dual purposes: rate limiting (security-critical) and application caching. The `allkeys-lru` eviction policy means that under memory pressure, rate-limiting keys can be evicted, effectively disabling rate limiting for some clients. There is no Redis Sentinel or Cluster for HA. If Redis goes down, rate limiting fails open (by design in `rate_limit.py:97-99`), and all cached data is lost.

**Evidence:**
- `docker-compose.prod.yml:57-61` -- Single Redis, `maxmemory 256mb`, `allkeys-lru`
- `backend/app/core/rate_limit.py:97-99` -- Fails open when Redis unavailable
- `backend/app/core/rate_limit.py:101` -- Rate limit keys use `rl:` prefix, same DB as cache
- No Redis Sentinel or Cluster configuration

**Risk:** Rate limiting can be silently disabled by cache pressure or Redis failure. No HA means a Redis crash affects both rate limiting and application performance simultaneously.

**Fix Plan:**
1. **Immediate:** Separate rate-limiting into Redis DB 1 (`redis://redis:6379/1`) and cache into DB 0 -- prevents LRU from evicting rate-limit keys
2. **Immediate:** Change eviction policy to `volatile-lru` so only keys with TTL are evicted (rate-limit keys already have TTL via `expire`)
3. **Short-term:** Add Redis persistence verification -- ensure AOF rewrite works correctly
4. **Medium-term:** Add Redis Sentinel for automatic failover (separate compose service)

**Acceptance Criteria:**
- Rate-limit keys are in a separate Redis database from cache keys
- Eviction policy changed to `volatile-lru`
- Rate limiting continues to work under cache pressure (verified by test)

**Test Plan:**
- Fill Redis DB 0 with cache data to trigger eviction, verify rate-limit keys in DB 1 survive
- Stop Redis, verify the application continues serving (degraded, no rate limit) and logs a warning
- Restart Redis, verify rate limiting resumes

**Effort:** 0.5-1 day

---

### Finding 6: CI/CD Lacks SAST and Container Image Scanning (P1 -- High)

**Description:**
The CI pipeline (`ci.yml`) runs linting (ruff, mypy, ESLint) and tests but has no SAST scanner (Bandit, Semgrep) for Python security issues (e.g., SQL injection, hardcoded secrets, insecure deserialization). The `security.yml` workflow runs Trivy in filesystem-scan mode only -- it does not scan the built Docker images, missing vulnerabilities in base images and installed packages. There is no DAST or dependency audit (`npm audit`, `pip-audit`) in the pipeline.

**Evidence:**
- `ci.yml` -- No `bandit`, `semgrep`, `pip-audit`, or `npm audit` steps
- `security.yml:29-40` -- Trivy scans filesystem only (`scan-type: fs`), not container images
- No image scanning step in `deploy.yml` before pushing to GHCR
- `backend/Dockerfile:26` -- `COPY --from=ghcr.io/astral-sh/uv:latest` uses `:latest` tag (mutable, unaudited)

**Risk:** Security vulnerabilities in dependencies or application code reach production undetected. Supply chain risk from unpinned `:latest` tags.

**Fix Plan:**
1. Add `bandit` scan step to `ci.yml` backend job: `uv run bandit -r app -c pyproject.toml`
2. Add `pip-audit` step: `uv run pip-audit --require-hashes --strict`
3. Add `npm audit` step to frontend CI
4. Add Trivy container image scan in `deploy.yml` after build, before push
5. Pin `ghcr.io/astral-sh/uv` to a specific digest in `backend/Dockerfile`
6. Consider adding Semgrep with DPP-relevant rules (injection, auth bypass)

**Acceptance Criteria:**
- CI fails on high/critical Bandit findings
- CI fails on high/critical pip-audit or npm audit findings
- Docker images are scanned before push to GHCR
- No `:latest` tags in production Dockerfiles

**Test Plan:**
- Introduce a known Bandit-flagged pattern, verify CI fails
- Add a dependency with a known CVE, verify pip-audit/npm audit fails
- Build an image with a vulnerable base, verify Trivy catches it

**Effort:** 1 day

---

### Finding 7: Frontend Production Container Runs as Root (P1 -- High)

**Description:**
The frontend production Dockerfile uses `nginx:alpine` as the final stage but never switches to a non-root user. The backend Dockerfile correctly creates and switches to `appuser` for the production stage (`backend/Dockerfile:59,73`), but the frontend omits this entirely. Running nginx as root inside the container increases the blast radius of any container escape or vulnerability.

Additionally, the frontend Dockerfile does not pin the `node:20-alpine` or `nginx:alpine` base image tags to specific digests, making builds non-reproducible and susceptible to supply chain attacks.

**Evidence:**
- `frontend/Dockerfile:56-67` -- Production stage uses `nginx:alpine`, no `USER` directive
- `frontend/Dockerfile:6` -- `FROM node:20-alpine as base` (no digest pin)
- `frontend/Dockerfile:56` -- `FROM nginx:alpine as production` (no digest pin)
- `backend/Dockerfile:59,73` -- Backend correctly uses `USER appuser` (good)

**Risk:** Container compromise leads to root access. Unpinned base images allow silent supply chain compromise.

**Fix Plan:**
1. Add `RUN chown -R nginx:nginx /usr/share/nginx/html && USER nginx` to the frontend production stage (nginx:alpine ships with a `nginx` user)
2. Pin all base images to digests: `FROM node:20-alpine@sha256:...`, `FROM nginx:alpine@sha256:...`
3. Pin `python:3.12-slim` in backend Dockerfile to digest as well
4. Add `HEALTHCHECK` instructions to both Dockerfiles

**Acceptance Criteria:**
- Frontend production container runs as non-root user
- All base images pinned to SHA256 digests
- Both Dockerfiles include HEALTHCHECK instructions
- Container still serves frontend correctly after changes

**Test Plan:**
- Build and run frontend container, verify `whoami` returns non-root
- Verify `docker inspect` shows the correct user
- Rebuild from pinned digests, verify image content matches
- Verify health check passes

**Effort:** 0.5 day

---

### Finding 8: Migration Runs in Startup Command with No Rollback Strategy (P2 -- Medium)

**Description:**
The production backend command (`docker-compose.prod.yml:177-179`) runs `alembic upgrade head` inline before starting uvicorn. While the migration env.py (`backend/app/db/migrations/env.py:52-66`) correctly uses `pg_advisory_lock(428197123)` to serialize concurrent migration attempts, the current single-container setup means migration only runs once. However, if the deployment is scaled to multiple backend containers (e.g., `--scale backend=2`), or if the deploy script is run concurrently (CI race condition), the advisory lock prevents corruption but both containers will block until the lock is released, delaying startup.

More critically, there is no **downgrade/rollback** mechanism. If a migration fails partway through, the database may be left in an inconsistent state with no automated recovery path.

**Evidence:**
- `docker-compose.prod.yml:177-179` -- Migration runs in container startup
- `backend/app/db/migrations/env.py:52-66` -- Advisory lock present (good), but no rollback on failure
- `backend/app/db/migrations/versions/0005_tenant_rls.py:29` -- DDL statements (`ALTER TABLE ENABLE ROW LEVEL SECURITY`) are not transactional in all cases
- Deploy script has no `alembic downgrade` step on failure

**Risk:** Failed migration can leave database in inconsistent state. No documented rollback procedure. Multi-container scaling blocked by inline migration.

**Fix Plan:**
1. Extract migration to a separate init container or pre-deploy step: `docker compose run --rm backend python -m alembic upgrade head`
2. Add migration verification step after running: check `alembic current` matches `alembic heads`
3. Document rollback procedure for each migration (many already have `downgrade()`)
4. Add a deploy script step that records the pre-deploy revision and can `alembic downgrade` on failure
5. Wrap DDL migrations in explicit transactions where possible

**Acceptance Criteria:**
- Migration runs as a separate step before backend container start
- Deploy script records pre-migration revision
- Failed migration triggers automatic downgrade to previous revision
- Documentation for manual rollback procedure

**Test Plan:**
- Deploy with a migration that intentionally fails, verify rollback
- Scale to 2 backend containers, verify both start successfully without migration conflicts
- Verify `alembic current` matches `alembic heads` after deploy

**Effort:** 1 day

---

### Finding 9: Plaintext Inter-Service Communication on Docker Bridge (P2 -- Medium)

**Description:**
All inter-service communication (backend -> Postgres, backend -> Redis, backend -> Keycloak, backend -> OPA, backend -> MinIO, Caddy -> backend, Caddy -> frontend, Caddy -> Keycloak) runs over plaintext HTTP/TCP on the Docker bridge network. While Caddy provides TLS termination for external traffic, the internal network is unencrypted. Database credentials, Redis passwords, OIDC tokens, and OPA policy decisions all traverse the bridge in cleartext.

On a single-host deployment (current Hetzner VPS), the Docker bridge network is local and the risk is lower. However, if services are ever split across hosts (e.g., managed database, separate Redis), this becomes a critical issue.

**Evidence:**
- `docker-compose.prod.yml:182` -- `DATABASE_URL=postgresql+asyncpg://...@postgres:5432/...` (no SSL)
- `docker-compose.prod.yml:183` -- `REDIS_URL=redis://:...@redis:6379/0` (no TLS)
- `docker-compose.prod.yml:189` -- `KEYCLOAK_ISSUER_URL_OVERRIDE=http://keycloak:8080/...` (plaintext)
- `docker-compose.prod.yml:191` -- `OPA_URL=http://opa:8181` (plaintext)
- `Caddyfile:7-16` -- `reverse_proxy backend:8000` (plaintext to backend)
- No `sslmode`, `--tls`, or certificate configuration for any internal connection

**Risk:** On single host, risk is low (Docker bridge is local). But any network sniffing on the host, compromised container, or future multi-host migration exposes credentials and tokens. Some compliance frameworks (SOC 2, ISO 27001) require encryption in transit for all sensitive data.

**Fix Plan:**
1. **Short-term (documentation):** Document the threat model -- single-host Docker bridge is acceptable for current deployment, but note the limitation
2. **Medium-term:** Enable `sslmode=require` for PostgreSQL connections and generate self-signed certs for Postgres
3. **Medium-term:** Enable Redis TLS (`--tls-port 6379 --tls-cert-file --tls-key-file`)
4. **Long-term:** Consider a service mesh (e.g., Docker Swarm overlay with encryption, or Linkerd) for mTLS

**Acceptance Criteria:**
- Threat model documented with explicit acceptance of plaintext on Docker bridge
- PostgreSQL connection uses `sslmode=require`
- Redis connection uses TLS
- Decision documented for Keycloak/OPA internal communication

**Test Plan:**
- Verify Postgres connections use SSL: `SELECT ssl FROM pg_stat_ssl`
- Verify Redis TLS: `redis-cli --tls --cert ... INFO server`
- Run `tcpdump` on Docker bridge, verify no plaintext credentials visible

**Effort:** 1-2 days

---

### Finding 10: No Load Testing or Performance Baseline in CI (P2 -- Medium)

**Description:**
There is no load testing in the CI/CD pipeline or as a manual process. There is no established performance baseline for key operations (DPP list, DPP publish, AASX export). Without a baseline, performance regressions are undetectable. The database pool is configured for 10 + 20 overflow connections (`config.py:48-49`), but it is unknown whether this is adequate for expected production load. The 4 uvicorn workers may be insufficient or excessive for the VPS resources.

**Evidence:**
- No `k6`, `locust`, `wrk`, or `ab` configuration in the repository
- `ci.yml`, `dpp-pipeline.yml` -- No performance test steps
- `backend/app/core/config.py:48-50` -- Pool size 10, overflow 20, timeout 30s (defaults, not benchmarked)
- `docker-compose.prod.yml:179` -- `--workers 4` (not validated against VPS resources)

**Risk:** Performance regressions reach production unnoticed. Database pool exhaustion under load causes cascading 503 errors. No capacity planning data.

**Fix Plan:**
1. Create a `k6` load test script covering critical endpoints: `GET /api/v1/tenants/{slug}/dpps`, `POST .../dpps`, `GET .../export/aasx/{id}`
2. Establish baseline: p50, p95, p99 latency and max RPS for each endpoint
3. Add load test as a manual CI workflow (`workflow_dispatch`) with results artifact upload
4. Tune pool size and worker count based on load test results
5. Set regression thresholds: fail if p99 > 2x baseline

**Acceptance Criteria:**
- k6 test script with at least 5 critical endpoint scenarios
- Documented performance baseline (p50, p95, p99, max RPS)
- CI workflow that can be triggered manually for regression testing
- Pool size and worker count justified by benchmark data

**Test Plan:**
- Run k6 against staging/local stack with 50 concurrent users
- Record metrics, establish baseline
- Introduce an intentional N+1 query, verify load test catches the regression
- Verify pool exhaustion scenario is handled gracefully (503, not crash)

**Effort:** 1-2 days

---

## Summary Table

| # | Finding | Severity | Effort | Files Affected |
|---|---------|----------|--------|----------------|
| 1 | No PostgreSQL backup/PITR | P0 | 1-2d | `docker-compose.prod.yml`, new backup config |
| 2 | Deploy causes downtime | P0 | 1-2d | `deploy.yml`, `docker-compose.prod.yml` |
| 3 | No observability (metrics/alerting) | P1 | 2-3d | `backend/app/main.py`, `docker-compose.prod.yml` |
| 4 | No container resource limits | P1 | 0.5d | `docker-compose.prod.yml` |
| 5 | Single Redis, shared rate-limit + cache | P1 | 0.5-1d | `docker-compose.prod.yml`, `rate_limit.py` |
| 6 | No SAST/image scanning in CI | P1 | 1d | `ci.yml`, `security.yml`, `deploy.yml`, Dockerfiles |
| 7 | Frontend container runs as root | P1 | 0.5d | `frontend/Dockerfile` |
| 8 | Migration in startup, no rollback | P2 | 1d | `docker-compose.prod.yml`, `deploy.yml`, `env.py` |
| 9 | Plaintext inter-service comms | P2 | 1-2d | `docker-compose.prod.yml`, `Caddyfile` |
| 10 | No load testing / perf baseline | P2 | 1-2d | New k6 scripts, `ci.yml` |

**Total estimated effort: 10-15 days**

---

## Positive Observations (Not Findings)

These are practices already done well that should be preserved:

- **Alembic advisory lock** (`env.py:52-66`): Multi-worker migration safety via `pg_advisory_lock(428197123)` is already implemented
- **Backend non-root user** (`backend/Dockerfile:59,73`): Production backend correctly creates and runs as `appuser`
- **Redis password in prod** (`docker-compose.prod.yml:62`): Production Redis uses `--requirepass` from env var
- **Prod config validation** (`config.py:259-281`): `model_validator` enforces encryption key, disables debug, requires explicit CORS in production
- **Trivy + SBOM** (`security.yml`): Filesystem vulnerability scanning and SBOM generation are already present
- **Health checks** on all infrastructure services (Postgres, Redis, Keycloak, OPA, MinIO) in both dev and prod compose files
- **`restart: unless-stopped`** on all prod services for crash recovery
- **Multi-stage builds** for both backend and frontend Dockerfiles separating dev/prod concerns
- **Caddy auto-TLS** for external traffic with HTTP/3 support (UDP port 443)
- **Rate limiter fails open** (`rate_limit.py:97-99`): Correct design -- rate limiting is defense-in-depth, not sole auth
