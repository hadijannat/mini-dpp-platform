# Mini DPP Platform

[![CI](https://github.com/hadijannat/mini-dpp-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/hadijannat/mini-dpp-platform/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/hadijannat/mini-dpp-platform)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](backend/pyproject.toml)
[![Node](https://img.shields.io/badge/node-20%2B-brightgreen)](frontend/package.json)

A Digital Product Passport (DPP) management platform based on the Asset Administration Shell (AAS) and IDTA DPP4.0 standards.

## Features

- **DPP Lifecycle Management**: Create, edit, publish, and archive Digital Product Passports
- **IDTA DPP4.0 Templates**: Support for all 6 standard submodel templates:
  - Digital Nameplate
  - Contact Information
  - Technical Data
  - Carbon Footprint
  - Handover Documentation
  - Hierarchical Structures
- **OIDC Authentication**: Keycloak integration for secure authentication
- **ABAC Authorization**: Open Policy Agent (OPA) for fine-grained access control
- **Catena-X Integration**: DTR (Digital Twin Registry) and EDC connector support
- **Export Formats**: AASX (IDTA Part 5 compliant) and JSON export
- **QR Code Generation**: Product identification via QR codes

## Tech Stack

### Backend
- Python 3.12+ with FastAPI
- SQLAlchemy 2.0 (async) with PostgreSQL
- Redis for caching
- Keycloak for OIDC
- OPA for ABAC policies

### Frontend
- React 18+ with TypeScript
- Vite build tool
- TailwindCSS
- React Query
- React Hook Form

### Infrastructure
- Docker Compose for local development
- PostgreSQL 16
- Redis 7
- Keycloak 24
- OPA (Open Policy Agent)
- MinIO (S3-compatible storage)

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 20+ (for frontend development)
- Python 3.12+ with uv (for backend development)

### Running with Docker Compose

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### Service URLs
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Keycloak Admin: http://localhost:8080/admin (admin/admin)
- OPA: http://localhost:8181

### Default Users
| Username | Password | Role |
|----------|----------|------|
| publisher@example.com | publisher123 | Publisher |
| viewer@example.com | viewer123 | Viewer |
| admin@example.com | admin123 | Admin |

## Development

### Backend Development

```bash
cd backend

# Install dependencies
uv sync

# Run migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn app.main:app --reload --port 8000

# Run tests
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .
uv run mypy app
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Run tests
npm test

# Lint
npm run lint

# Type check
npm run typecheck

# Build for production
npm run build
```

## Project Structure

```
mini-dpp-platform/
├── backend/
│   ├── app/
│   │   ├── core/           # Config, logging, security
│   │   ├── db/             # Models, migrations, session
│   │   └── modules/        # Feature modules
│   │       ├── templates/  # Template registry
│   │       ├── dpps/       # DPP management
│   │       ├── export/     # AASX/JSON export
│   │       ├── qr/         # QR code generation
│   │       ├── policies/   # ABAC policies
│   │       └── connectors/ # External integrations
│   └── tests/
├── frontend/
│   └── src/
│       ├── app/            # Layouts, routing
│       ├── auth/           # Authentication
│       ├── components/     # Shared components
│       └── features/       # Feature modules
├── infra/
│   ├── keycloak/          # Realm configuration
│   ├── opa/               # Policy files
│   └── postgres/          # Init scripts
└── docker-compose.yml
```

## API Endpoints

### Templates
- `GET /api/v1/templates` - List available templates
- `GET /api/v1/templates/{key}` - Get template details
- `GET /api/v1/templates/{key}/schema` - Get UI schema

### DPPs
- `POST /api/v1/dpps` - Create new DPP
- `GET /api/v1/dpps` - List DPPs
- `GET /api/v1/dpps/{id}` - Get DPP details
- `PUT /api/v1/dpps/{id}` - Update DPP
- `POST /api/v1/dpps/{id}/publish` - Publish DPP
- `POST /api/v1/dpps/{id}/archive` - Archive DPP

### Export
- `GET /api/v1/export/{dpp_id}/aasx` - Export as AASX
- `GET /api/v1/export/{dpp_id}/json` - Export as JSON

### QR Codes
- `GET /api/v1/qr/{dpp_id}` - Generate QR code

### Connectors
- `GET /api/v1/connectors` - List connectors
- `POST /api/v1/connectors` - Create connector
- `POST /api/v1/connectors/{id}/test` - Test connector
- `POST /api/v1/connectors/{id}/publish/{dpp_id}` - Publish DPP to DTR

## Standards Compliance

- **IDTA 2002-1-0**: Asset Administration Shell - Part 1
- **IDTA 2006-2-0**: Digital Nameplate
- **IDTA 2002-4-0**: AAS JSON Serialization
- **IDTA Part 5**: AASX Package Format
- **DPP4.0**: Digital Product Passport Submodel Templates

## License

MIT License
