# Getting Started

This guide covers first-run setup, startup options, default users, and a practical walkthrough using the existing documentation storyboard assets.

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Git
- Optional for local workflows: Python 3.12+, Node.js 20+

## Startup Paths

### Path A (Recommended): Full Docker Compose Stack

```bash
git clone https://github.com/hadijannat/mini-dpp-platform.git
cd mini-dpp-platform

cp .env.example .env
docker compose up -d
```

Check health:

```bash
docker compose ps
curl -fsS http://localhost:8000/health
```

Notes:

- Backend migrations run automatically at container start.
- Use `docker compose up -d --build` on first run or when Dockerfiles/dependencies change.
- You can override host ports with `.env` values such as `BACKEND_HOST_PORT` and `KEYCLOAK_HOST_PORT`.

### Path B: Run App Code Locally, Keep Infra in Docker

Start infra dependencies:

```bash
docker compose up -d postgres redis keycloak opa minio
```

Run backend locally:

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

Run frontend locally (set required Vite variables):

```bash
cd frontend
npm ci
VITE_API_BASE_URL=http://localhost:8000 \
VITE_KEYCLOAK_URL=http://localhost:8080 \
VITE_KEYCLOAK_REALM=dpp-platform \
VITE_KEYCLOAK_CLIENT_ID=dpp-frontend \
npm run dev
```

## Default URLs (Compose Defaults)

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API Docs | http://localhost:8000/api/v1/docs |
| API Health | http://localhost:8000/health |
| Keycloak | http://localhost:8080 |
| MinIO Console | http://localhost:9001 |

## Default Demo Users (Realm Import)

| Username | Password | Typical Role |
|---|---|---|
| `admin` | `admin123` | platform admin |
| `publisher` | `publisher123` | publisher |
| `viewer` | `viewer123` | viewer |

## First-Run Workflow

1. Sign in as `admin` and create or inspect tenants.
2. Sign in as `publisher` and switch to a tenant.
3. Refresh templates from the templates page.
4. Create a DPP from one or more templates.
5. Open a submodel editor and save values.
6. Publish the DPP and verify the viewer route.

## Walkthrough: Multi-Tenant Flow (Storyboard)

<details>
<summary>View storyboard steps (11 screenshots)</summary>

| Step | Screenshot |
|---|---|
| 1. Login page | ![Login](../assets/storyboard/01-login.png) |
| 2. Keycloak sign-in | ![Keycloak](../assets/storyboard/02-keycloak-login.png) |
| 3. Admin dashboard | ![Dashboard](../assets/storyboard/03-admin-dashboard.png) |
| 4. Tenants list | ![Tenants](../assets/storyboard/04-tenants-list.png) |
| 5. Create tenants | ![Create tenant](../assets/storyboard/05-create-tenant.png) |
| 6. Add publisher to tenant | ![Add member](../assets/storyboard/06-tenant-members.png) |
| 7. Switch as publisher | ![Switcher](../assets/storyboard/07-publisher-tenant-switcher.png) |
| 8. Create DPP | ![Create DPP](../assets/storyboard/08-create-dpp.png) |
| 9. DPP list in tenant | ![Alpha DPPs](../assets/storyboard/09-dpp-list-alpha.png) |
| 10. Another tenant is empty | ![Beta empty](../assets/storyboard/10-dpp-list-beta-empty.png) |
| 11. Public viewer route | ![Viewer](../assets/storyboard/11-viewer-route.png) |

</details>

## Walkthrough: Dynamic Forms Flow

<details>
<summary>View storyboard steps (5 screenshots)</summary>

| Step | Screenshot |
|---|---|
| 12. Select templates | ![Template selection](../assets/storyboard/12-template-selection.png) |
| 13. DPP appears in list | ![DPP list](../assets/storyboard/13-dpp-list-new.png) |
| 14. Open submodel edit links | ![Edit links](../assets/storyboard/14-dpp-submodels-edit.png) |
| 15. Carbon footprint form | ![Carbon form](../assets/storyboard/15-carbon-footprint-form.png) |
| 16. Nameplate form | ![Nameplate form](../assets/storyboard/16-nameplate-form.png) |

</details>

## Additional UI References

### Admin: Global Asset ID Prefix

- Settings page: ![Admin settings page](../assets/images/admin-id-prefix-01-settings.png)
- Edit action: ![Edit base URI](../assets/images/admin-id-prefix-02-edit.png)
- Saved state: ![Settings saved](../assets/images/admin-id-prefix-03-saved.png)

### Data Carriers

![Data Carriers page](../assets/images/data_carriers.png)

## Quick API Smoke Sequence (Optional)

Fetch token:

```bash
TOKEN=$(curl -s -X POST "http://localhost:8080/realms/dpp-platform/protocol/openid-connect/token" \
  -d "client_id=dpp-backend" \
  -d "client_secret=backend-secret-dev" \
  -d "username=publisher" \
  -d "password=publisher123" \
  -d "grant_type=password" | jq -r '.access_token')
```

List templates:

```bash
curl -s "http://localhost:8000/api/v1/templates" \
  -H "Authorization: Bearer $TOKEN"
```

## Next Reads

- Architecture: [`../architecture/README.md`](../architecture/README.md)
- Operations: [`../operations/README.md`](../operations/README.md)
- Release process: [`../releases/release-guide.md`](../releases/release-guide.md)
