"""
API Router for Connector management endpoints.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from app.core.audit import emit_audit_event
from app.core.security import require_access
from app.core.tenancy import TenantPublisher
from app.db.models import ConnectorType
from app.db.session import DbSession
from app.modules.connectors.catenax.service import CatenaXConnectorService
from app.modules.connectors.edc.client import EDCConfig, EDCManagementClient
from app.modules.connectors.edc.contract_service import EDCContractService
from app.modules.connectors.edc.health import check_edc_health
from app.modules.dpps.service import DPPService

router = APIRouter()


def _connector_resource(connector: Any) -> dict[str, Any]:
    """Build ABAC resource context for a connector."""
    return {
        "type": "connector",
        "id": str(connector.id),
        "owner_subject": connector.created_by_subject,
        "status": connector.status.value
        if hasattr(connector.status, "value")
        else str(connector.status),
    }


class ConnectorCreateRequest(BaseModel):
    """Request model for creating a connector."""

    name: str
    config: dict[str, Any]


class ConnectorResponse(BaseModel):
    """Response model for connector data."""

    id: UUID
    name: str
    connector_type: str
    status: str
    last_tested_at: str | None
    last_test_result: dict[str, Any] | None
    created_at: str

    class Config:
        from_attributes = True


class ConnectorListResponse(BaseModel):
    """Response model for list of connectors."""

    connectors: list[ConnectorResponse]
    count: int


class TestResultResponse(BaseModel):
    """Response model for connector test result."""

    status: str
    error_message: str | None = None
    dtr_url: str | None = None
    auth_type: str | None = None


class PublishResultResponse(BaseModel):
    """Response model for DPP publish result."""

    status: str
    action: str | None = None
    shell_id: str | None = None
    error_message: str | None = None


class EDCPublishResultResponse(BaseModel):
    """Response model for EDC dataspace publish result."""

    status: str
    asset_id: str | None = None
    access_policy_id: str | None = None
    usage_policy_id: str | None = None
    contract_definition_id: str | None = None
    error_message: str | None = None


class EDCStatusResponse(BaseModel):
    """Response model for EDC dataspace status check."""

    registered: bool
    asset_id: str | None = None
    error: str | None = None


class EDCHealthResponse(BaseModel):
    """Response model for EDC health check."""

    status: str
    edc_version: str | None = None
    error_message: str | None = None


@router.get("", response_model=ConnectorListResponse)
async def list_connectors(
    db: DbSession,
    tenant: TenantPublisher,
    connector_type: ConnectorType | None = Query(None, description="Filter by connector type"),
) -> ConnectorListResponse:
    """
    List all connectors.

    Requires publisher role.
    """
    await require_access(tenant.user, "list", {"type": "connector"}, tenant=tenant)
    service = CatenaXConnectorService(db)
    connectors = await service.get_connectors(tenant.tenant_id, connector_type)

    return ConnectorListResponse(
        connectors=[
            ConnectorResponse(
                id=c.id,
                name=c.name,
                connector_type=c.connector_type.value,
                status=c.status.value,
                last_tested_at=c.last_tested_at.isoformat() if c.last_tested_at else None,
                last_test_result=c.last_test_result,
                created_at=c.created_at.isoformat(),
            )
            for c in connectors
        ],
        count=len(connectors),
    )


@router.post("", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
async def create_connector(
    request: ConnectorCreateRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> ConnectorResponse:
    """
    Create a new Catena-X connector.

    Config should include:
    - dtr_base_url: DTR API base URL
    - auth_type: "oidc" or "token"
    - client_id, client_secret (for OIDC)
    - token (for token auth)
    - bpn: Business Partner Number
    - submodel_base_url: URL where submodels are exposed
    - edc_dsp_endpoint: Optional EDC DSP endpoint
    """
    await require_access(tenant.user, "create", {"type": "connector"}, tenant=tenant)
    service = CatenaXConnectorService(db)

    connector = await service.create_connector(
        tenant_id=tenant.tenant_id,
        name=request.name,
        config=request.config,
        created_by_subject=tenant.user.sub,
    )
    await db.commit()

    return ConnectorResponse(
        id=connector.id,
        name=connector.name,
        connector_type=connector.connector_type.value,
        status=connector.status.value,
        last_tested_at=None,
        last_test_result=None,
        created_at=connector.created_at.isoformat(),
    )


@router.get("/{connector_id}", response_model=ConnectorResponse)
async def get_connector(
    connector_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> ConnectorResponse:
    """
    Get a specific connector by ID.
    """
    service = CatenaXConnectorService(db)
    connector = await service.get_connector(connector_id, tenant.tenant_id)

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {connector_id} not found",
        )

    await require_access(tenant.user, "read", _connector_resource(connector), tenant=tenant)

    return ConnectorResponse(
        id=connector.id,
        name=connector.name,
        connector_type=connector.connector_type.value,
        status=connector.status.value,
        last_tested_at=connector.last_tested_at.isoformat() if connector.last_tested_at else None,
        last_test_result=connector.last_test_result,
        created_at=connector.created_at.isoformat(),
    )


@router.post("/{connector_id}/test", response_model=TestResultResponse)
async def test_connector(
    connector_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> TestResultResponse:
    """
    Test connectivity for a connector.

    Verifies DTR endpoint is reachable and authentication is valid.
    """
    service = CatenaXConnectorService(db)
    connector = await service.get_connector(connector_id, tenant.tenant_id)
    if not connector:
        return TestResultResponse(
            status="error",
            error_message="Connector not found",
        )

    await require_access(tenant.user, "test", _connector_resource(connector), tenant=tenant)

    result = await service.test_connector(connector_id, tenant.tenant_id)
    await db.commit()

    return TestResultResponse(
        status=result.get("status", "error"),
        error_message=result.get("error_message"),
        dtr_url=result.get("dtr_url"),
        auth_type=result.get("auth_type"),
    )


@router.post("/{connector_id}/publish/{dpp_id}", response_model=PublishResultResponse)
async def publish_dpp_to_connector(
    connector_id: UUID,
    dpp_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> PublishResultResponse:
    """
    Publish a DPP to a connector's Digital Twin Registry.

    The DPP must be published first. Creates or updates
    the shell descriptor in the DTR.
    """
    service = CatenaXConnectorService(db)

    dpp_service = DPPService(db)
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        return PublishResultResponse(
            status="error",
            error_message=f"DPP {dpp_id} not found",
        )

    await require_access(
        tenant.user,
        "publish_to_connector",
        {
            "type": "dpp",
            "id": str(dpp.id),
            "owner_subject": dpp.owner_subject,
            "status": dpp.status.value,
        },
        tenant=tenant,
    )

    try:
        result = await service.publish_dpp_to_dtr(connector_id, dpp_id, tenant.tenant_id)
        await emit_audit_event(
            db_session=db,
            action="publish_to_dtr",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
            metadata={
                "connector_id": str(connector_id),
                "dtr_status": result.get("status", "error"),
                "action": result.get("action"),
            },
        )
        return PublishResultResponse(
            status=result.get("status", "error"),
            action=result.get("action"),
            shell_id=result.get("shell_id"),
        )
    except ValueError as e:
        return PublishResultResponse(
            status="error",
            error_message=str(e),
        )


# =============================================================================
# EDC Dataspace Endpoints
# =============================================================================


@router.post(
    "/{connector_id}/dataspace/publish/{dpp_id}",
    response_model=EDCPublishResultResponse,
)
async def publish_dpp_to_dataspace(
    connector_id: UUID,
    dpp_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> EDCPublishResultResponse:
    """
    Publish a DPP to an Eclipse Dataspace via EDC.

    Creates an EDC asset, access and usage policies, and a contract
    definition so data consumers can discover and negotiate access.
    The DPP must be published first.
    """
    dpp_service = DPPService(db)
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        return EDCPublishResultResponse(
            status="error",
            error_message=f"DPP {dpp_id} not found",
        )

    await require_access(
        tenant.user,
        "publish_to_connector",
        {
            "type": "dpp",
            "id": str(dpp.id),
            "owner_subject": dpp.owner_subject,
            "status": dpp.status.value,
        },
        tenant=tenant,
    )

    service = EDCContractService(db)
    result = await service.publish_to_dataspace(dpp_id, connector_id, tenant.tenant_id)

    await emit_audit_event(
        db_session=db,
        action="publish_to_edc",
        resource_type="dpp",
        resource_id=dpp_id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={
            "connector_id": str(connector_id),
            "edc_status": result.status,
            "asset_id": result.asset_id,
        },
    )

    return EDCPublishResultResponse(
        status=result.status,
        asset_id=result.asset_id,
        access_policy_id=result.access_policy_id,
        usage_policy_id=result.usage_policy_id,
        contract_definition_id=result.contract_definition_id,
        error_message=result.error_message,
    )


@router.get(
    "/{connector_id}/dataspace/status/{dpp_id}",
    response_model=EDCStatusResponse,
)
async def get_dataspace_status(
    connector_id: UUID,
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> EDCStatusResponse:
    """
    Check whether a DPP is registered in the EDC catalog.
    """
    service = EDCContractService(db)
    result = await service.get_dataspace_status(dpp_id, connector_id, tenant.tenant_id)

    return EDCStatusResponse(
        registered=result.get("registered", False),
        asset_id=result.get("asset_id"),
        error=result.get("error"),
    )


@router.get(
    "/{connector_id}/dataspace/health",
    response_model=EDCHealthResponse,
)
async def check_connector_edc_health(
    connector_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> EDCHealthResponse:
    """
    Check EDC controlplane health for a connector.
    """
    cx_service = CatenaXConnectorService(db)
    connector = await cx_service.get_connector(connector_id, tenant.tenant_id)

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {connector_id} not found",
        )

    await require_access(tenant.user, "read", _connector_resource(connector), tenant=tenant)

    config = connector.config
    edc_config = EDCConfig(
        management_url=config.get("edc_management_url", ""),
        api_key=config.get("edc_management_api_key", ""),
    )

    client = EDCManagementClient(edc_config)
    try:
        result = await check_edc_health(client)
    finally:
        await client.close()

    return EDCHealthResponse(
        status=result.get("status", "error"),
        edc_version=result.get("edc_version"),
        error_message=result.get("error_message"),
    )
