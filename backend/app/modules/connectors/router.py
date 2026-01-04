"""
API Router for Connector management endpoints.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.core.security import Publisher
from app.db.models import ConnectorType
from app.db.session import DbSession
from app.modules.connectors.catenax.service import CatenaXConnectorService

router = APIRouter()


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


@router.get("", response_model=ConnectorListResponse)
async def list_connectors(
    db: DbSession,
    _user: Publisher,
    connector_type: ConnectorType | None = Query(None, description="Filter by connector type"),
) -> ConnectorListResponse:
    """
    List all connectors.

    Requires publisher role.
    """
    service = CatenaXConnectorService(db)
    connectors = await service.get_connectors(connector_type)

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
    user: Publisher,
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
    service = CatenaXConnectorService(db)

    connector = await service.create_connector(
        name=request.name,
        config=request.config,
        created_by_subject=user.sub,
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
    _user: Publisher,
) -> ConnectorResponse:
    """
    Get a specific connector by ID.
    """
    service = CatenaXConnectorService(db)
    connector = await service.get_connector(connector_id)

    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {connector_id} not found",
        )

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
    _user: Publisher,
) -> TestResultResponse:
    """
    Test connectivity for a connector.

    Verifies DTR endpoint is reachable and authentication is valid.
    """
    service = CatenaXConnectorService(db)
    result = await service.test_connector(connector_id)
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
    db: DbSession,
    _user: Publisher,
) -> PublishResultResponse:
    """
    Publish a DPP to a connector's Digital Twin Registry.

    The DPP must be published first. Creates or updates
    the shell descriptor in the DTR.
    """
    service = CatenaXConnectorService(db)

    try:
        result = await service.publish_dpp_to_dtr(connector_id, dpp_id)
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
