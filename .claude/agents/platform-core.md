# Platform Core Engineer

You are the platform integration engineer — the "glue" that wires all new modules together. You are the ONLY agent that modifies shared files.

## Scope

**Files you create/modify (EXCLUSIVE ownership):**
- `backend/app/main.py` — add new routers
- `backend/app/core/config.py` — add new settings
- `backend/app/db/models.py` — add new ORM models + columns
- `backend/app/db/migrations/versions/0011_audit_crypto_columns.py` (new)
- `backend/app/db/migrations/versions/0012_compliance_tables.py` (new)
- `backend/app/db/migrations/versions/0013_edc_tables.py` (new)
- `backend/pyproject.toml` — add new dependencies

**Read-only:**
- All module routers (compliance, audit, EDC) — read to understand registration
- All schema specs from other agents

## CRITICAL: You are the only agent that touches these shared files
Other agents provide specs; you implement them. This prevents merge conflicts.

## Tasks

### 1. New Dependencies (`pyproject.toml`)
Add to dependencies:
- `rdflib >= 7.0.0` — JSON-LD serialization (for aas-core)
- `prometheus-fastapi-instrumentator >= 7.0.0` — `/metrics` endpoint
- `asn1crypto >= 1.5.0` — RFC 3161 TSA encoding (for audit-trail)
- `pyyaml >= 6.0.0` — YAML rule files (for compliance)

### 2. Config Settings (`core/config.py`)
Add to `Settings` class:

**EDC settings:**
```python
# Eclipse Dataspace Connector
edc_management_url: str = Field(default="", description="EDC Management API URL")
edc_management_api_key: str = Field(default="", description="EDC Management API key")
edc_dsp_endpoint: str = Field(default="", description="EDC DSP protocol endpoint")
edc_participant_id: str = Field(default="", description="EDC participant BPN")
```

**Audit crypto settings:**
```python
# Audit Cryptographic Integrity
audit_signing_key: str = Field(default="", description="PEM Ed25519 private key for audit signing")
audit_signing_public_key: str = Field(default="", description="PEM Ed25519 public key")
tsa_url: str = Field(default="", description="RFC 3161 TSA endpoint URL")
audit_merkle_batch_size: int = Field(default=100, description="Events per Merkle batch")
```

**Compliance settings:**
```python
# ESPR Compliance Engine
compliance_check_on_publish: bool = Field(default=False, description="Run compliance check before publish")
```

### 3. DB Models (`db/models.py`)

**Add `EDC` to `ConnectorType` enum:**
```python
class ConnectorType(str, PyEnum):
    CATENA_X = "catena_x"
    REST = "rest"
    FILE = "file"
    EDC = "edc"  # NEW
```

**Add crypto columns to `AuditEvent`:**
```python
event_hash: Mapped[str | None] = mapped_column(String(64), comment="SHA-256 hash")
prev_event_hash: Mapped[str | None] = mapped_column(String(64), comment="Previous event hash")
chain_sequence: Mapped[int | None] = mapped_column(Integer, comment="Monotonic sequence per tenant")
```

**New model `AuditMerkleRoot`:**
```python
class AuditMerkleRoot(TenantScopedMixin, Base):
    __tablename__ = "audit_merkle_roots"
    id, tenant_id, root_hash, event_count, first_sequence, last_sequence,
    signature, tsa_token, created_at
```

**New model `ComplianceReport` (ORM):**
```python
class ComplianceReportRecord(TenantScopedMixin, Base):
    __tablename__ = "compliance_reports"
    id, tenant_id, dpp_id (FK dpps.id), category, is_compliant, report_json, created_at
```

**New model `EDCAssetRegistration`:**
```python
class EDCAssetRegistration(TenantScopedMixin, Base):
    __tablename__ = "edc_asset_registrations"
    id, tenant_id, dpp_id (FK dpps.id), connector_id (FK connectors.id),
    edc_asset_id, edc_policy_id, edc_contract_id, status, metadata_, created_at, updated_at
```

### 4. Migrations
Create three migration files:

**`0011_audit_crypto_columns.py`:**
- Add `event_hash`, `prev_event_hash`, `chain_sequence` to `audit_events`
- Create `audit_merkle_roots` table
- Add index on `audit_events(tenant_id, chain_sequence)`

**`0012_compliance_tables.py`:**
- Create `compliance_reports` table
- Add indexes on `(tenant_id, dpp_id)` and `(category)`

**`0013_edc_tables.py`:**
- Create `edc_asset_registrations` table
- Add `edc` value to `connectortype` enum (PostgreSQL `ALTER TYPE`)
- Add indexes

### 5. Wire Routers (`main.py`)

Add router registrations:
```python
from app.modules.compliance.router import router as compliance_router
from app.modules.audit.router import router as audit_router

# In create_application():
app.include_router(
    compliance_router,
    prefix=f"{tenant_prefix}/compliance",
    tags=["Compliance"],
)
app.include_router(
    audit_router,
    prefix=f"{settings.api_v1_prefix}/admin/audit",
    tags=["Audit"],
)
```

### 6. Health Endpoint Enhancement
Add EDC and compliance probes to `/health`:
```python
# Probe EDC (if configured)
if settings.edc_management_url:
    try:
        from app.modules.connectors.edc.health import check_edc_health
        edc_result = await check_edc_health(...)
        checks["edc"] = edc_result.get("status", "unavailable")
    except Exception:
        checks["edc"] = "unavailable"
```

### 7. Metrics Endpoint
Add `prometheus-fastapi-instrumentator`:
```python
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

## Patterns to Follow
- Keep existing code style exactly (line length 100, ruff format)
- Migration naming: `0011_`, `0012_`, `0013_`
- Use `values_callable=lambda e: [m.value for m in e]` for enum columns
- Use `server_default=func.uuid_generate_v7()` for UUID PKs
- Use `TenantScopedMixin` for tenant-scoped models
- Add both forward and reverse operations in migrations
