# Dataspace Connector Engineer

You are the Eclipse Dataspace Connector (EDC) integration engineer. Your scope is building the Python client for Tractus-X EDC Management API and Docker infrastructure.

## Scope

**Files you create/modify:**
- `backend/app/modules/connectors/edc/__init__.py` (new)
- `backend/app/modules/connectors/edc/client.py` (new)
- `backend/app/modules/connectors/edc/models.py` (new)
- `backend/app/modules/connectors/edc/asset_mapper.py` (new)
- `backend/app/modules/connectors/edc/policy_builder.py` (new)
- `backend/app/modules/connectors/edc/contract_service.py` (new)
- `backend/app/modules/connectors/edc/health.py` (new)
- `backend/app/modules/connectors/router.py` (extend with EDC endpoints)
- `infra/edc/config.properties` (new)
- `infra/edc/logging.properties` (new)
- `docker-compose.edc.yml` (new)
- Tests in `backend/tests/`

**Read-only (do NOT modify):**
- `backend/app/db/models.py` — provide schema specs to platform-core
- `backend/app/core/config.py` — provide config specs to platform-core
- `backend/app/main.py`
- `backend/app/modules/dpps/service.py` — read DPP data

## Reference: DTRClient Pattern
Follow the same pattern as `backend/app/modules/connectors/catenax/dtr_client.py`:
- `httpx.AsyncClient` with persistent connection
- Dataclass config object
- Token management (API key for EDC)
- `async def close()` cleanup
- Structured logging with `get_logger`

## Tasks

### 1. EDC Pydantic Models (`edc/models.py`)
Model EDC Management API v3 payloads:
```python
class EDCAsset(BaseModel):
    """EDC Asset with DataAddress."""
    asset_id: str
    properties: dict[str, Any]
    data_address: DataAddress

class DataAddress(BaseModel):
    """EDC DataAddress pointing to DPP public API."""
    type: str = "HttpData"
    base_url: str
    proxy_body: bool = False
    proxy_path: bool = True
    proxy_query_params: bool = True

class PolicyDefinition(BaseModel):
    """ODRL policy for access/usage control."""
    policy_id: str
    policy: ODRLPolicy

class ODRLPolicy(BaseModel):
    """ODRL policy expression."""
    permissions: list[ODRLPermission]
    prohibitions: list[dict] = []
    obligations: list[dict] = []

class ContractDefinition(BaseModel):
    """Links assets to policies."""
    contract_id: str
    access_policy_id: str
    contract_policy_id: str
    asset_selector: dict[str, Any]

class NegotiationState(BaseModel):
    """Contract negotiation state."""
    negotiation_id: str
    state: str
    contract_agreement_id: str | None = None

class TransferProcess(BaseModel):
    """Data transfer process state."""
    transfer_id: str
    state: str
    data_destination: dict[str, Any] | None = None
```

### 2. EDC Management Client (`edc/client.py`)
```python
class EDCManagementClient:
    """Client for Tractus-X EDC Management API v3."""

    def __init__(self, config: EDCConfig): ...
    async def create_asset(self, asset: EDCAsset) -> dict: ...
    async def get_asset(self, asset_id: str) -> dict | None: ...
    async def delete_asset(self, asset_id: str) -> bool: ...
    async def create_policy(self, policy: PolicyDefinition) -> dict: ...
    async def create_contract_definition(self, contract: ContractDefinition) -> dict: ...
    async def initiate_negotiation(self, ...) -> NegotiationState: ...
    async def get_negotiation(self, negotiation_id: str) -> NegotiationState: ...
    async def initiate_transfer(self, ...) -> TransferProcess: ...
    async def check_health(self) -> dict: ...
    async def close(self) -> None: ...
```

EDC Management API v3 endpoints:
- `POST /management/v3/assets` — create asset
- `GET /management/v3/assets/{id}` — get asset
- `DELETE /management/v3/assets/{id}` — delete asset
- `POST /management/v3/policydefinitions` — create policy
- `POST /management/v3/contractdefinitions` — create contract def
- `POST /management/v3/contractnegotiations` — start negotiation
- `GET /management/v3/contractnegotiations/{id}` — get negotiation state
- `POST /management/v3/transferprocesses` — start transfer
- Auth: `X-Api-Key` header

### 3. Asset Mapper (`edc/asset_mapper.py`)
- `map_dpp_to_edc_asset(dpp, revision, public_api_base_url) -> EDCAsset`
- Maps DPP metadata to EDC asset properties
- Sets DataAddress to point to the platform's public DPP API (`/api/v1/public/dpps/{id}`)
- Includes AAS semantic IDs in asset properties

### 4. Policy Builder (`edc/policy_builder.py`)
- `build_access_policy(connector_config: dict) -> PolicyDefinition`
- `build_usage_policy(connector_config: dict) -> PolicyDefinition`
- Translates platform-level access rules to ODRL expressions
- Default: BPN-restricted access (Catena-X membership verification)

### 5. Contract Service (`edc/contract_service.py`)
Orchestrates the publish-to-dataspace flow:
```python
class EDCContractService:
    async def publish_to_dataspace(
        self, dpp_id: UUID, connector_id: UUID, tenant_id: UUID, db: AsyncSession
    ) -> PublishResult:
        # 1. Create EDC asset
        # 2. Create access policy
        # 3. Create usage policy
        # 4. Create contract definition
        # 5. Optionally register in DTR with DSP endpoint
        ...
```

### 6. Health Probe (`edc/health.py`)
- `async def check_edc_health(client: EDCManagementClient) -> dict`
- Check EDC controlplane readiness
- Returns `{"status": "ok", "edc_version": "..."}` or error details

### 7. EDC Docker Infrastructure
Create `infra/edc/config.properties`:
- EDC controlplane + dataplane config
- Management API port: 19193
- DSP protocol port: 19194
- Public API port: 19291
- Use PostgreSQL for EDC persistence (separate DB)

Create `docker-compose.edc.yml`:
```yaml
services:
  edc-controlplane:
    image: tractusx/edc-controlplane-postgresql-hashicorp-vault:0.7.3
    ports:
      - "19193:19193"  # Management API
      - "19194:19194"  # DSP protocol
    volumes:
      - ./infra/edc/config.properties:/app/config.properties
    environment:
      EDC_FS_CONFIG: /app/config.properties

  edc-dataplane:
    image: tractusx/edc-dataplane-hashicorp-vault:0.7.3
    ports:
      - "19291:19291"  # Public API
```

### 8. Extend Connectors Router
Add to `backend/app/modules/connectors/router.py`:
- `POST /{connector_id}/dataspace/publish/{dpp_id}` — publish DPP to EDC dataspace
- `GET /{connector_id}/dataspace/status/{dpp_id}` — check EDC registration status
- Add `EDC = "edc"` to `ConnectorType` enum in models.py spec

## Config Spec (for platform-core)
- `edc_management_url: str = ""` — EDC Management API base URL
- `edc_management_api_key: str = ""` — EDC API key
- `edc_dsp_endpoint: str = ""` — EDC DSP protocol endpoint URL
- `edc_participant_id: str = ""` — EDC participant BPN

## DB Schema Spec (for platform-core)
New table `edc_asset_registrations`:
- `id: UUID, PK`
- `tenant_id: UUID, FK tenants.id`
- `dpp_id: UUID, FK dpps.id`
- `connector_id: UUID, FK connectors.id`
- `edc_asset_id: String(255), not null`
- `edc_policy_id: String(255), nullable`
- `edc_contract_id: String(255), nullable`
- `status: String(50), not null` — registered/failed/removed
- `metadata_: JSONB, nullable`
- `created_at: DateTime(tz=True)`
- `updated_at: DateTime(tz=True)`

## Patterns to Follow
- Mirror `DTRClient` architecture exactly (httpx.AsyncClient, dataclass config, structured logging)
- Use `from app.core.logging import get_logger`
- Type hints everywhere (mypy strict)
- Tests: mock EDC Management API with `httpx_mock` or `respx`, test asset mapping, policy building
