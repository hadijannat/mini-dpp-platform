"""
API Router for Connector management endpoints.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel

from app.core.audit import emit_audit_event
from app.core.config import get_settings
from app.core.encryption import ConnectorConfigEncryptor, EncryptionError
from app.core.security import require_access
from app.core.security.actor_metadata import actor_payload, load_users_by_subject
from app.core.security.resource_context import (
    build_connector_resource_context,
    build_dpp_resource_context,
)
from app.core.tenancy import TenantPublisher
from app.db.models import ConnectorType
from app.db.session import DbSession
from app.modules.connectors.catenax.service import CatenaXConnectorService
from app.modules.connectors.edc.client import EDCConfig, EDCManagementClient
from app.modules.connectors.edc.contract_service import EDCContractService
from app.modules.connectors.edc.health import check_edc_health
from app.modules.dpps.service import DPPService

router = APIRouter()


class ActorSummary(BaseModel):
    """Actor identity summary for ownership metadata."""

    subject: str
    display_name: str | None = None
    email_masked: str | None = None


class AccessSummary(BaseModel):
    """Current user's effective access to a connector resource."""

    can_read: bool
    can_update: bool
    can_publish: bool
    can_archive: bool
    source: str


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
    created_by_subject: str
    created_by: ActorSummary
    visibility_scope: str
    access: AccessSummary
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


_LEGACY_SUNSET = "Sat, 31 Jan 2027 23:59:59 GMT"


def _add_legacy_deprecation_headers(response: Response) -> None:
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = _LEGACY_SUNSET
    response.headers["Link"] = (
        '</api/v1/tenants/{tenant_slug}/dataspace/connectors>; rel="successor-version"'
    )


def _decrypt_connector_config(config: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.encryption_master_key:
        return config
    try:
        return ConnectorConfigEncryptor(settings.encryption_master_key).decrypt_config(config)
    except EncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to decrypt connector config: {exc}",
        ) from exc


def _connector_access_source(
    *,
    tenant: TenantPublisher,
    creator_subject: str,
    shared_with_current_user: bool,
) -> str:
    if (
        tenant.is_tenant_admin
        and tenant.user.sub != creator_subject
        and not shared_with_current_user
    ):
        return "tenant_admin"
    if shared_with_current_user and tenant.user.sub != creator_subject:
        return "share"
    return "owner"


def _connector_response_payload(
    connector: Any,
    *,
    tenant: TenantPublisher,
    created_by: dict[str, str | None],
    shared_with_current_user: bool,
) -> ConnectorResponse:
    is_owner = connector.created_by_subject == tenant.user.sub
    can_mutate = tenant.is_tenant_admin or is_owner
    return ConnectorResponse(
        id=connector.id,
        name=connector.name,
        connector_type=connector.connector_type.value,
        status=connector.status.value,
        created_by_subject=connector.created_by_subject,
        created_by=ActorSummary(**created_by),
        visibility_scope=(
            connector.visibility_scope.value
            if hasattr(connector.visibility_scope, "value")
            else str(connector.visibility_scope)
        ),
        access=AccessSummary(
            can_read=True,
            can_update=can_mutate,
            can_publish=can_mutate,
            can_archive=can_mutate,
            source=_connector_access_source(
                tenant=tenant,
                creator_subject=connector.created_by_subject,
                shared_with_current_user=shared_with_current_user,
            ),
        ),
        last_tested_at=connector.last_tested_at.isoformat() if connector.last_tested_at else None,
        last_test_result=connector.last_test_result,
        created_at=connector.created_at.isoformat(),
    )


@router.get("", response_model=ConnectorListResponse)
async def list_connectors(
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
    connector_type: ConnectorType | None = Query(None, description="Filter by connector type"),
    scope: str = Query("mine", description="mine, shared, or all accessible connectors"),
) -> ConnectorListResponse:
    """
    List all connectors.

    Requires publisher role.
    """
    service = CatenaXConnectorService(db)
    normalized_scope = scope if scope in {"mine", "shared", "all"} else "mine"
    connectors, shared_ids = await service.get_connectors_for_subject(
        tenant_id=tenant.tenant_id,
        user_subject=tenant.user.sub,
        is_tenant_admin=tenant.is_tenant_admin,
        scope=normalized_scope,
        connector_type=connector_type,
    )
    users = await load_users_by_subject(db, [c.created_by_subject for c in connectors])

    await emit_audit_event(
        db_session=db,
        action="list_connectors",
        resource_type="connector",
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"count": len(connectors), "scope": normalized_scope},
    )

    return ConnectorListResponse(
        connectors=[
            _connector_response_payload(
                c,
                tenant=tenant,
                created_by=actor_payload(c.created_by_subject, users),
                shared_with_current_user=c.id in shared_ids,
            )
            for c in connectors
        ],
        count=len(connectors),
    )


@router.post("", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
async def create_connector(
    body: ConnectorCreateRequest,
    response: Response,
    http_request: Request,
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
    settings = get_settings()
    if not settings.dataspace_legacy_connector_write_enabled:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "Legacy connector write endpoint is disabled. "
                "Use /api/v1/tenants/{tenant_slug}/dataspace/connectors."
            ),
        )

    await require_access(tenant.user, "create", {"type": "connector"}, tenant=tenant)
    service = CatenaXConnectorService(db)
    _add_legacy_deprecation_headers(response)

    connector = await service.create_connector(
        tenant_id=tenant.tenant_id,
        name=body.name,
        config=body.config,
        created_by_subject=tenant.user.sub,
    )
    await db.commit()
    users = await load_users_by_subject(db, [connector.created_by_subject])
    await emit_audit_event(
        db_session=db,
        action="create_connector",
        resource_type="connector",
        resource_id=str(connector.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=http_request,
    )

    return _connector_response_payload(
        connector,
        tenant=tenant,
        created_by=actor_payload(connector.created_by_subject, users),
        shared_with_current_user=False,
    )


@router.get("/{connector_id}", response_model=ConnectorResponse)
async def get_connector(
    connector_id: UUID,
    request: Request,
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

    shared_with_current_user = await service.is_connector_shared_with_user(
        tenant_id=tenant.tenant_id,
        connector_id=connector.id,
        user_subject=tenant.user.sub,
    )
    await require_access(
        tenant.user,
        "read",
        build_connector_resource_context(
            connector,
            shared_with_current_user=shared_with_current_user,
        ),
        tenant=tenant,
    )
    users = await load_users_by_subject(db, [connector.created_by_subject])
    await emit_audit_event(
        db_session=db,
        action="read_connector",
        resource_type="connector",
        resource_id=str(connector.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
    )
    return _connector_response_payload(
        connector,
        tenant=tenant,
        created_by=actor_payload(connector.created_by_subject, users),
        shared_with_current_user=shared_with_current_user,
    )


@router.post("/{connector_id}/test", response_model=TestResultResponse)
async def test_connector(
    connector_id: UUID,
    request: Request,
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

    shared_with_current_user = await service.is_connector_shared_with_user(
        tenant_id=tenant.tenant_id,
        connector_id=connector.id,
        user_subject=tenant.user.sub,
    )
    await require_access(
        tenant.user,
        "test",
        build_connector_resource_context(
            connector,
            shared_with_current_user=shared_with_current_user,
        ),
        tenant=tenant,
    )

    result = await service.test_connector(connector_id, tenant.tenant_id)
    await db.commit()
    await emit_audit_event(
        db_session=db,
        action="test_connector",
        resource_type="connector",
        resource_id=str(connector.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"status": result.get("status", "error")},
    )

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
    response: Response,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> PublishResultResponse:
    """
    Publish a DPP to a connector's Digital Twin Registry.

    The DPP must be published first. Creates or updates
    the shell descriptor in the DTR.
    """
    settings = get_settings()
    if not settings.dataspace_legacy_connector_write_enabled:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "Legacy connector publish endpoint is disabled. "
                "Use /api/v1/tenants/{tenant_slug}/dataspace/assets/publish."
            ),
        )

    service = CatenaXConnectorService(db)
    _add_legacy_deprecation_headers(response)
    connector = await service.get_connector(connector_id, tenant.tenant_id)
    if not connector:
        return PublishResultResponse(
            status="error",
            error_message=f"Connector {connector_id} not found",
        )
    shared_connector = await service.is_connector_shared_with_user(
        tenant_id=tenant.tenant_id,
        connector_id=connector.id,
        user_subject=tenant.user.sub,
    )
    await require_access(
        tenant.user,
        "read",
        build_connector_resource_context(
            connector,
            shared_with_current_user=shared_connector,
        ),
        tenant=tenant,
    )

    dpp_service = DPPService(db)
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        return PublishResultResponse(
            status="error",
            error_message=f"DPP {dpp_id} not found",
        )
    shared_dpp = await dpp_service.is_resource_shared_with_user(
        tenant_id=tenant.tenant_id,
        resource_type="dpp",
        resource_id=dpp.id,
        user_subject=tenant.user.sub,
    )

    await require_access(
        tenant.user,
        "publish_to_connector",
        build_dpp_resource_context(
            dpp,
            shared_with_current_user=shared_dpp,
        ),
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
    response: Response,
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
    settings = get_settings()
    if not settings.dataspace_legacy_connector_write_enabled:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "Legacy dataspace publish endpoint is disabled. "
                "Use /api/v1/tenants/{tenant_slug}/dataspace/assets/publish."
            ),
        )

    dpp_service = DPPService(db)
    _add_legacy_deprecation_headers(response)
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        return EDCPublishResultResponse(
            status="error",
            error_message=f"DPP {dpp_id} not found",
        )
    shared_dpp = await dpp_service.is_resource_shared_with_user(
        tenant_id=tenant.tenant_id,
        resource_type="dpp",
        resource_id=dpp.id,
        user_subject=tenant.user.sub,
    )

    await require_access(
        tenant.user,
        "publish_to_connector",
        build_dpp_resource_context(
            dpp,
            shared_with_current_user=shared_dpp,
        ),
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
    cx_service = CatenaXConnectorService(db)
    connector = await cx_service.get_connector(connector_id, tenant.tenant_id)
    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {connector_id} not found",
        )
    shared_connector = await cx_service.is_connector_shared_with_user(
        tenant_id=tenant.tenant_id,
        connector_id=connector.id,
        user_subject=tenant.user.sub,
    )
    await require_access(
        tenant.user,
        "read",
        build_connector_resource_context(
            connector,
            shared_with_current_user=shared_connector,
        ),
        tenant=tenant,
    )

    dpp_service = DPPService(db)
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )
    shared_dpp = await dpp_service.is_resource_shared_with_user(
        tenant_id=tenant.tenant_id,
        resource_type="dpp",
        resource_id=dpp.id,
        user_subject=tenant.user.sub,
    )
    await require_access(
        tenant.user,
        "read",
        build_dpp_resource_context(
            dpp,
            shared_with_current_user=shared_dpp,
        ),
        tenant=tenant,
    )

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
    request: Request,
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

    shared_with_current_user = await cx_service.is_connector_shared_with_user(
        tenant_id=tenant.tenant_id,
        connector_id=connector.id,
        user_subject=tenant.user.sub,
    )
    await require_access(
        tenant.user,
        "read",
        build_connector_resource_context(
            connector,
            shared_with_current_user=shared_with_current_user,
        ),
        tenant=tenant,
    )

    config = _decrypt_connector_config(connector.config)
    edc_config = EDCConfig(
        management_url=config.get("edc_management_url", ""),
        api_key=config.get("edc_management_api_key", ""),
    )

    client = EDCManagementClient(edc_config)
    try:
        result = await check_edc_health(client)
    finally:
        await client.close()

    await emit_audit_event(
        db_session=db,
        action="check_connector_edc_health",
        resource_type="connector",
        resource_id=str(connector.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"status": result.get("status", "error")},
    )

    return EDCHealthResponse(
        status=result.get("status", "error"),
        edc_version=result.get("edc_version"),
        error_message=result.get("error_message"),
    )
