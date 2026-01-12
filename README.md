# Mini DPP Platform

[![CI](https://github.com/hadijannat/mini-dpp-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/hadijannat/mini-dpp-platform/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](backend/pyproject.toml)
[![Node](https://img.shields.io/badge/node-20%2B-brightgreen)](frontend/package.json)

> **A production-ready Digital Product Passport (DPP) platform built on Asset Administration Shell (AAS) and IDTA DPP4.0 standards.**

Create, manage, and publish Digital Product Passports with enterprise-grade auth, multi-tenant isolation, template-driven dynamic forms, and AASX/JSON exports.

---

## ✨ Highlights

- 🔐 **Enterprise Auth + ABAC** — Keycloak OIDC + OPA policies
- 🏢 **Multi‑Tenant by Design** — tenant-scoped APIs, UI switcher, and `tenant_admin` role
- 🧩 **Template‑Driven Forms** — UI generated from IDTA Submodel Templates (SMT)
- 📦 **DPP Lifecycle** — Draft → Edit → Publish → Archive, with revision history
- 🧱 **DPP Masters & Versioned Templates** — product‑level masters with placeholders and `latest` alias
- 🔁 **ERP‑Friendly Import** — one‑shot JSON import from released master templates
- 🔗 **Catena‑X Ready** — DTR publishing with optional EDC DSP metadata
- 📤 **Export & Data Carriers** — AASX, JSON, QR and GS1 Digital Link

---

## ⚡ Quick Start (Docker)

### Prerequisites
- Docker + Docker Compose
- Ports: `5173`, `8000`, `8081`, `5432`

### Start the stack

```bash
git clone https://github.com/hadijannat/mini-dpp-platform.git
cd mini-dpp-platform

docker compose up -d

# Run database migrations (first start)
docker exec dpp-backend alembic upgrade head
```

### Access points

| Service | URL | Notes |
|---------|-----|-------|
| Frontend | http://localhost:5173 | UI (tenant aware) |
| API Docs | http://localhost:8000/api/v1/docs | Swagger UI (or `BACKEND_HOST_PORT` from `.env`) |
| Keycloak | http://localhost:8081/admin | admin / admin |

### Default users

| Username | Password | Role | Notes |
|----------|----------|------|------|
| `admin` | `admin123` | platform admin | Full platform access |
| `publisher` | `publisher123` | publisher | Create/manage DPPs |
| `viewer` | `viewer123` | viewer | View published DPPs |

> `tenant_admin` is a tenant‑scoped role you can assign via tenant membership.

---

## 🧭 Walkthroughs (Visual Storyboards)

### 🧭 Multi‑Tenant Walkthrough (Docker Demo)

This walkthrough uses **two tenants** (`alpha` and `beta`). Create tenants as `admin`,
assign the `publisher` to `alpha`, then build a tenant‑scoped DPP.

**Step 1:** Login page
![Multi‑tenant demo login page](docs/storyboard/01-login.png)

**Step 2:** Authenticate with Keycloak
![Keycloak sign‑in](docs/storyboard/02-keycloak-login.png)

**Step 3:** Admin dashboard
![Admin dashboard](docs/storyboard/03-admin-dashboard.png)

**Step 4:** Open Tenants
![Tenants list](docs/storyboard/04-tenants-list.png)

**Step 5:** Create `alpha` and `beta`
![Create tenant modal](docs/storyboard/05-create-tenant.png)

**Step 6:** Add publisher membership to `alpha`
Use the **publisher user subject (OIDC sub)** when adding members.
![Add tenant member](docs/storyboard/06-tenant-members.png)

**Step 7:** Switch to `alpha` as publisher
![Tenant switcher](docs/storyboard/07-publisher-tenant-switcher.png)

**Step 8:** Create a DPP in `alpha`
![Create DPP modal](docs/storyboard/08-create-dpp.png)

**Step 9:** Verify tenant‑scoped list (`alpha`)
![DPP list for alpha](docs/storyboard/09-dpp-list-alpha.png)

**Step 10:** Confirm `beta` is empty
![DPP list for beta](docs/storyboard/10-dpp-list-beta-empty.png)

**Step 11:** Open tenant viewer route
Example route: `/t/alpha/dpp/{dpp_id}`
![Viewer route](docs/storyboard/11-viewer-route.png)

---

### 🧩 Template‑Driven Editor (Dynamic Forms)

Templates generate the UI. Select multiple templates, create a DPP, and edit each
submodel with its own dynamic form.

**Step 12:** Select templates during DPP creation
![Template selection modal](docs/storyboard/12-template-selection.png)

**Step 13:** DPP created in the list
![DPP list with new draft](docs/storyboard/13-dpp-list-new.png)

**Step 14:** Submodels with per‑template edit links
![DPP detail with edit links](docs/storyboard/14-dpp-submodels-edit.png)

**Step 15:** Carbon Footprint form (lists + nested sections)
![Carbon footprint dynamic form](docs/storyboard/15-carbon-footprint-form.png)

**Step 16:** Nameplate form (multi‑language + file inputs)
![Nameplate dynamic form](docs/storyboard/16-nameplate-form.png)

---

### 🔧 Admin Walkthrough: Global Asset ID Prefix

Change the HTTP prefix used for global asset IDs (e.g., `https://example.com/asset/*`).

**Step A:** Open Settings
![Admin settings page](docs/images/admin-id-prefix-01-settings.png)

**Step B:** Edit the prefix (must start with `http://` and end with `/`)
![Edit base URI](docs/images/admin-id-prefix-02-edit.png)

**Step C:** Save and verify
![Settings saved](docs/images/admin-id-prefix-03-saved.png)

---

### 📦 Data Carriers (QR / GS1 Digital Link)

![Data Carriers page](docs/images/data_carriers.png)

- Standard QR encodes the viewer URL
- GS1 Digital Link format: `https://id.gs1.org/01/{GTIN}/21/{serial}`
- QR generation is available for **published** DPPs

---

## 🧠 How Template‑Driven Forms Work

- Templates are fetched from the **IDTA Submodel Template repository** and cached.
- The backend parses templates via **BaSyx SDK**, generating:
  - a **definition AST** (submodel tree)
  - a **JSON schema** for UI rendering
- The frontend renders each submodel dynamically and enforces SMT qualifiers
  (cardinality, allowed ranges, read‑only, required languages, etc.).

---

## 📡 API Usage

### Get access token

```bash
TOKEN=$(curl -s -X POST "http://localhost:8081/realms/dpp-platform/protocol/openid-connect/token" \
  -d "client_id=dpp-backend" \
  -d "client_secret=backend-secret-dev" \
  -d "username=publisher" \
  -d "password=publisher123" \
  -d "grant_type=password" | jq -r '.access_token')
```

### Refresh templates (IDTA)

```bash
curl -X POST "http://localhost:8000/api/v1/templates/refresh" \
  -H "Authorization: Bearer $TOKEN"
```

### Create a DPP (tenant‑scoped)

> Tenant APIs use `/api/v1/tenants/{tenant}`. Default tenant: `default`.

```bash
curl -X POST "http://localhost:8000/api/v1/tenants/default/dpps" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_ids": {
      "manufacturerPartId": "MOTOR-DRIVE-3000",
      "serialNumber": "SN-2024-API-001"
    },
    "selected_templates": ["digital-nameplate", "technical-data"]
  }'
```

### DPP Masters: fetch released template + variables

```bash
curl -X GET "http://localhost:8000/api/v1/tenants/default/masters/by-product/MOTOR-DRIVE-3000/versions/latest/template" \
  -H "Authorization: Bearer $TOKEN"

curl -X GET "http://localhost:8000/api/v1/tenants/default/masters/by-product/MOTOR-DRIVE-3000/versions/latest/variables" \
  -H "Authorization: Bearer $TOKEN"
```

### Import a DPP from a master template (single shot)

```bash
curl -X POST "http://localhost:8000/api/v1/tenants/default/dpps/import?master_product_id=MOTOR-DRIVE-3000&master_version=latest" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @filled-template.json
```

> The UI now includes a “Import from Master Template” panel to load a released master,
> fill placeholders, and import a serialized DPP without additional UI in the source system.

### Publish a DPP

```bash
curl -X POST "http://localhost:8000/api/v1/tenants/default/dpps/{dpp_id}/publish" \
  -H "Authorization: Bearer $TOKEN"
```

### Export as AASX

```bash
curl -O -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/tenants/default/export/{dpp_id}/aasx"
```

---

## 🧪 Template Diagnostics

Generate a conformance report (schema coverage + qualifier support):

```bash
docker compose exec -T backend python -m app.modules.templates.diagnostics > /tmp/template-report.json
```

---

## 🧪 Template Goldens (Snapshots)

Golden files lock the **template definition + schema** hashes so we can detect
unexpected changes in dynamic form generation.

### Update goldens

```bash
docker compose up -d
docker exec dpp-backend alembic upgrade head

# Backend runs on 8001 in docker-compose by default
cd backend
DPP_BASE_URL=http://localhost:8001 uv run python -m tests.tools.update_template_goldens
```

### Run golden checks

```bash
cd backend
RUN_E2E=1 RUN_GOLDENS=1 DPP_BASE_URL=http://localhost:8001 KEYCLOAK_BASE_URL=http://localhost:8081 \
  uv run pytest -m golden --run-e2e --run-goldens
```

---

## 📋 API Endpoints (Summary)

### Tenants
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/tenants/mine` | List my tenants |
| GET | `/api/v1/tenants` | List all tenants (platform admin) |
| POST | `/api/v1/tenants` | Create tenant (platform admin) |
| GET | `/api/v1/tenants/{tenant}` | Get tenant details |
| GET | `/api/v1/tenants/{tenant}/members` | List tenant members |
| POST | `/api/v1/tenants/{tenant}/members` | Add tenant member |
| DELETE | `/api/v1/tenants/{tenant}/members/{user_subject}` | Remove tenant member |

### Templates
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/templates` | List templates |
| GET | `/api/v1/templates/{key}` | Template metadata |
| GET | `/api/v1/templates/{key}/definition` | Template definition AST |
| GET | `/api/v1/templates/{key}/schema` | Template UI schema |
| POST | `/api/v1/templates/refresh` | Refresh all templates |
| POST | `/api/v1/templates/refresh/{key}` | Refresh a single template |

### DPPs
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/tenants/{tenant}/dpps` | Create DPP |
| GET | `/api/v1/tenants/{tenant}/dpps` | List DPPs |
| GET | `/api/v1/tenants/{tenant}/dpps/{id}` | Get DPP |
| PUT | `/api/v1/tenants/{tenant}/dpps/{id}/submodel` | Update submodel data |
| POST | `/api/v1/tenants/{tenant}/dpps/{id}/publish` | Publish DPP |

### Export & Data Carriers
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/tenants/{tenant}/export/{id}/aasx` | Export AASX |
| GET | `/api/v1/tenants/{tenant}/export/{id}/json` | Export JSON |
| GET | `/api/v1/tenants/{tenant}/qr/{id}` | Basic QR code |
| POST | `/api/v1/tenants/{tenant}/qr/{id}/carrier` | Custom data carrier |
| GET | `/api/v1/tenants/{tenant}/qr/{id}/gs1` | GS1 Digital Link URL |

---

## 🧱 Project Structure

```
mini-dpp-platform/
├── backend/
│   ├── app/
│   │   ├── core/           # Config, logging, security
│   │   ├── db/             # Models, migrations
│   │   └── modules/        # Feature modules
│   │       ├── templates/  # IDTA template registry + diagnostics
│   │       ├── dpps/       # DPP lifecycle management
│   │       ├── export/     # AASX/JSON export
│   │       ├── qr/         # QR code generation
│   │       └── connectors/ # Catena-X integration
│   └── tests/
├── frontend/
│   └── src/
│       ├── features/       # Feature modules
│       └── components/     # Shared UI components
├── infra/
│   ├── keycloak/          # Realm configuration
│   └── opa/               # ABAC policies
└── docker-compose.yml
```

---

## 🔧 Troubleshooting

### Templates not loading / `UndefinedTableError`
**Cause:** Database migrations haven't been run.

```bash
docker exec dpp-backend alembic upgrade head
```

### Login credentials not working
**Cause:** Keycloak might have stale data from a previous installation.

```bash
docker compose down -v
docker compose up -d
docker exec dpp-backend alembic upgrade head
```

### Port conflicts
Set custom ports in `.env`:

```bash
cp .env.example .env
# Edit KEYCLOAK_HOST_PORT, BACKEND_HOST_PORT as needed
```

---

## 📜 Standards Alignment

This platform is aligned with:
- **AAS (IDTA 01001/01002)** and **AASX (IDTA 01005)**
- **IDTA DPP4.0 templates** (Digital Nameplate, Carbon Footprint, etc.)
- **GS1 Digital Link** for data carriers

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `cd backend && uv run pytest`
4. Submit a pull request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Built for the circular economy 🌱</strong>
</p>
