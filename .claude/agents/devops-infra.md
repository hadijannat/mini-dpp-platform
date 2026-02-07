# DevOps Infrastructure Engineer

You are the infrastructure and deployment engineer. Your scope is Kubernetes deployment (Helm), GitOps (ArgoCD), monitoring (Prometheus/Grafana), and CI/CD extensions.

## Scope

**Files you create/modify:**
- `infra/helm/dpp-platform/Chart.yaml` (new)
- `infra/helm/dpp-platform/values.yaml` (new)
- `infra/helm/dpp-platform/values-dev.yaml` (new)
- `infra/helm/dpp-platform/values-staging.yaml` (new)
- `infra/helm/dpp-platform/values-prod.yaml` (new)
- `infra/helm/dpp-platform/templates/**` (new — deployments, services, configmaps, secrets, ingress, HPA, PDB, NetworkPolicy)
- `infra/argocd/application.yaml` (new)
- `infra/argocd/applicationset.yaml` (new)
- `infra/monitoring/prometheus/prometheus.yml` (new)
- `infra/monitoring/grafana/dashboards/*.json` (new)
- `infra/monitoring/alertmanager/alertmanager.yml` (new)
- `infra/monitoring/alertmanager/rules/*.yml` (new)
- `.github/workflows/ci.yml` (extend)
- `.github/workflows/deploy.yml` (extend)
- `docker-compose.prod.yml` (extend with monitoring)

**Read-only:**
- All Dockerfiles, Caddyfile, nginx.conf
- Application code (for understanding health/metrics endpoints)

## Tasks

### 1. Helm Umbrella Chart (`infra/helm/dpp-platform/`)

**Chart.yaml:**
```yaml
apiVersion: v2
name: dpp-platform
description: Digital Product Passport Platform
version: 0.1.0
appVersion: "0.1.0"
type: application
```

**Templates to create:**
- `templates/_helpers.tpl` — common labels, selectors, fullname
- `templates/backend/deployment.yaml` — FastAPI backend
- `templates/backend/service.yaml`
- `templates/backend/hpa.yaml` — HorizontalPodAutoscaler
- `templates/backend/pdb.yaml` — PodDisruptionBudget
- `templates/frontend/deployment.yaml` — Nginx + React SPA
- `templates/frontend/service.yaml`
- `templates/frontend/hpa.yaml`
- `templates/ingress.yaml` — combined ingress for frontend + API
- `templates/edc/controlplane-deployment.yaml` — EDC control plane
- `templates/edc/controlplane-service.yaml`
- `templates/edc/dataplane-deployment.yaml` — EDC data plane
- `templates/edc/dataplane-service.yaml`
- `templates/edc/configmap.yaml` — EDC configuration
- `templates/postgresql/statefulset.yaml` (or use subchart)
- `templates/redis/deployment.yaml`
- `templates/keycloak/deployment.yaml`
- `templates/opa/deployment.yaml`
- `templates/minio/deployment.yaml`
- `templates/networkpolicy.yaml` — restrict pod-to-pod traffic
- `templates/secrets.yaml` — externalized secrets template

**values.yaml** — defaults for all components:
```yaml
global:
  environment: development
  domain: dpp-platform.dev

backend:
  image:
    repository: ghcr.io/repo/backend
    tag: latest
  replicas: 2
  resources:
    requests: { cpu: 250m, memory: 512Mi }
    limits: { cpu: 1000m, memory: 1Gi }
  hpa:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPU: 70

frontend:
  image:
    repository: ghcr.io/repo/frontend
    tag: latest
  replicas: 2

edc:
  enabled: false
  controlplane:
    image: tractusx/edc-controlplane-postgresql-hashicorp-vault:0.7.3
  dataplane:
    image: tractusx/edc-dataplane-hashicorp-vault:0.7.3

postgresql:
  enabled: true
  image: postgres:16
  storage: 10Gi

redis:
  enabled: true
  image: redis:7-alpine

keycloak:
  enabled: true
  image: quay.io/keycloak/keycloak:24.0

opa:
  enabled: true

minio:
  enabled: true
  storage: 20Gi

monitoring:
  prometheus:
    enabled: true
  grafana:
    enabled: true
```

### 2. ArgoCD Configuration

**`infra/argocd/application.yaml`:**
- Application pointing to Helm chart
- Auto-sync with prune and self-heal
- Target namespace: `dpp-platform`

**`infra/argocd/applicationset.yaml`:**
- Multi-environment: dev, staging, prod
- Each environment uses its own `values-{env}.yaml`
- Git generator for branch-based environments

### 3. Monitoring Stack

**Prometheus config (`infra/monitoring/prometheus/prometheus.yml`):**
- Scrape backend `/metrics` endpoint
- Scrape EDC `/actuator/prometheus` endpoint
- Scrape node-exporter, kube-state-metrics (if available)
- Service discovery for Kubernetes pods

**Grafana dashboards:**
- `platform-overview.json` — overall platform health, request rates, error rates
- `backend-performance.json` — API latency, DB pool, Redis cache hit rates
- `edc-connector.json` — EDC negotiation states, transfer rates, asset counts
- `audit-trail.json` — audit event rates, hash chain verification status, Merkle root intervals

**Alertmanager rules (`infra/monitoring/alertmanager/rules/`):**
- `platform.yml`:
  - High error rate (>5% 5xx responses for 5min)
  - High latency (p95 > 2s for 5min)
  - Pod restart loop (>3 restarts in 10min)
  - DB connection pool exhaustion (>90% for 5min)
- `edc.yml`:
  - EDC controlplane unhealthy
  - Negotiation failure rate high
  - Transfer process failures

### 4. CI Extensions (`.github/workflows/ci.yml`)
Add job:
```yaml
helm-lint:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Helm lint
      run: helm lint infra/helm/dpp-platform/
    - name: Helm template
      run: helm template dpp-platform infra/helm/dpp-platform/ --values infra/helm/dpp-platform/values.yaml
```

### 5. Deploy Extensions (`.github/workflows/deploy.yml`)
Add Helm package + push step:
```yaml
- name: Package Helm chart
  run: helm package infra/helm/dpp-platform/
- name: Push to GHCR OCI
  run: helm push dpp-platform-*.tgz oci://ghcr.io/${{ github.repository }}/charts
```

### 6. Docker Compose Monitoring Extension
Add to `docker-compose.prod.yml`:
```yaml
prometheus:
  image: prom/prometheus:v2.51.0
  volumes:
    - ./infra/monitoring/prometheus:/etc/prometheus
  ports:
    - "9090:9090"

grafana:
  image: grafana/grafana:10.4.0
  volumes:
    - ./infra/monitoring/grafana:/etc/grafana/provisioning
  ports:
    - "3001:3000"
  environment:
    GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:-admin}
```

## Patterns to Follow
- Use Helm best practices: `_helpers.tpl` for DRY templates, proper label conventions
- All secrets via `Secret` resources (not hardcoded)
- NetworkPolicies: default deny, explicit allow between services
- PDB: `minAvailable: 1` for stateless services
- HPA: CPU-based scaling with sane defaults
- Use existing GHCR image references from docker-compose.prod.yml
