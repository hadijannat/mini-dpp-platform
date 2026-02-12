"""API router for dataspace control-plane endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.audit import emit_audit_event
from app.core.security import require_access
from app.core.security.resource_context import (
    build_connector_resource_context,
    build_dpp_resource_context,
)
from app.core.tenancy import TenantPublisher
from app.db.models import DataspacePolicyTemplateState
from app.db.session import DbSession
from app.modules.dataspace.schemas import (
    AssetPublicationListResponse,
    AssetPublicationResponse,
    AssetPublishRequest,
    CatalogEntry,
    CatalogQueryRequest,
    CatalogQueryResponse,
    CatenaXDTRRuntimeConfig,
    ConformanceRunListResponse,
    ConformanceRunRequest,
    ConformanceRunResponse,
    ConnectorManifest,
    ConnectorValidationResponse,
    DataspaceConnectorCreateRequest,
    DataspaceConnectorListResponse,
    DataspaceConnectorResponse,
    DataspaceConnectorUpdateRequest,
    EDCRuntimeConfig,
    ManifestApplyResponse,
    ManifestDiffResponse,
    NegotiationCreateRequest,
    NegotiationListResponse,
    NegotiationResponse,
    PolicyTemplateCreateRequest,
    PolicyTemplateListResponse,
    PolicyTemplateResponse,
    PolicyTemplateUpdateRequest,
    RegulatoryEvidenceResponse,
    TransferCreateRequest,
    TransferListResponse,
    TransferResponse,
)
from app.modules.dataspace.service import DataspaceService, DataspaceServiceError
from app.modules.dpps.service import DPPService

router = APIRouter()


def _as_http_error(exc: DataspaceServiceError) -> HTTPException:
    text = str(exc)
    if " not found" in text:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=text)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=text)


def _connector_response(
    connector: Any,
    *,
    secret_refs: list[str],
) -> DataspaceConnectorResponse:
    runtime_config: EDCRuntimeConfig | CatenaXDTRRuntimeConfig
    if connector.runtime.value == "edc":
        runtime_config = EDCRuntimeConfig.model_validate(connector.runtime_config)
    elif connector.runtime.value == "catena_x_dtr":
        runtime_config = CatenaXDTRRuntimeConfig.model_validate(connector.runtime_config)
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unsupported runtime in connector record: {connector.runtime.value}",
        )

    return DataspaceConnectorResponse(
        id=connector.id,
        name=connector.name,
        runtime=connector.runtime.value,
        participant_id=connector.participant_id,
        display_name=connector.display_name,
        status=connector.status.value,
        runtime_config=runtime_config,
        secret_refs=secret_refs,
        created_by_subject=connector.created_by_subject,
        last_validated_at=connector.last_validated_at,
        last_validation_result=connector.last_validation_result,
        created_at=connector.created_at,
        updated_at=connector.updated_at,
    )


def _catalog_entries(raw: dict[str, Any]) -> list[CatalogEntry]:
    datasets = raw.get("dcat:dataset") or raw.get("dataset") or []
    if isinstance(datasets, dict):
        datasets = [datasets]
    if not isinstance(datasets, list):
        return []

    entries: list[CatalogEntry] = []
    for item in datasets:
        if not isinstance(item, dict):
            continue
        entries.append(
            CatalogEntry(
                id=str(item.get("@id") or item.get("id") or "unknown"),
                title=item.get("dct:title") or item.get("title"),
                description=item.get("dct:description") or item.get("description"),
                asset_id=item.get("asset:prop:id") or item.get("assetId"),
                policy=item.get("odrl:hasPolicy") or item.get("policy"),
                raw=item,
            )
        )
    return entries


def _policy_template_response(template: Any) -> PolicyTemplateResponse:
    return PolicyTemplateResponse(
        id=template.id,
        name=template.name,
        version=template.version,
        state=template.state.value,
        description=template.description,
        policy=template.policy,
        created_by_subject=template.created_by_subject,
        approved_by_subject=template.approved_by_subject,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _asset_publication_response(publication: Any) -> AssetPublicationResponse:
    return AssetPublicationResponse(
        id=publication.id,
        status=publication.status,
        dpp_id=publication.dpp_id,
        connector_id=publication.connector_id,
        asset_id=publication.asset_id,
        access_policy_id=publication.access_policy_id,
        usage_policy_id=publication.usage_policy_id,
        contract_definition_id=publication.contract_definition_id,
        created_at=publication.created_at,
        updated_at=publication.updated_at,
    )


def _negotiation_response(negotiation: Any) -> NegotiationResponse:
    return NegotiationResponse(
        id=negotiation.id,
        connector_id=negotiation.connector_id,
        publication_id=negotiation.publication_id,
        negotiation_id=negotiation.negotiation_id,
        state=negotiation.state,
        contract_agreement_id=negotiation.contract_agreement_id,
        created_at=negotiation.created_at,
        updated_at=negotiation.updated_at,
    )


def _transfer_response(transfer: Any) -> TransferResponse:
    return TransferResponse(
        id=transfer.id,
        connector_id=transfer.connector_id,
        negotiation_id=transfer.negotiation_id,
        transfer_id=transfer.transfer_id,
        state=transfer.state,
        data_destination=transfer.data_destination,
        created_at=transfer.created_at,
        updated_at=transfer.updated_at,
    )


@router.post(
    "/connectors",
    response_model=DataspaceConnectorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataspace_connector(
    body: DataspaceConnectorCreateRequest,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> DataspaceConnectorResponse:
    """Create a dataspace connector instance using strict v2 schemas."""
    await require_access(tenant.user, "create", {"type": "connector"}, tenant=tenant)

    service = DataspaceService(db)
    try:
        connector, secret_refs = await service.create_connector(
            tenant_id=tenant.tenant_id,
            body=body,
            created_by_subject=tenant.user.sub,
        )
    except DataspaceServiceError as exc:
        raise _as_http_error(exc) from exc

    await db.commit()

    await emit_audit_event(
        db_session=db,
        action="create_dataspace_connector",
        resource_type="dataspace_connector",
        resource_id=str(connector.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"runtime": connector.runtime.value},
    )

    return _connector_response(connector, secret_refs=secret_refs)


@router.get(
    "/connectors",
    response_model=DataspaceConnectorListResponse,
)
async def list_dataspace_connectors(
    db: DbSession,
    tenant: TenantPublisher,
) -> DataspaceConnectorListResponse:
    """List dataspace connectors for the active tenant."""
    await require_access(tenant.user, "list", {"type": "connector"}, tenant=tenant)
    service = DataspaceService(db)
    connectors = await service.list_connectors(tenant_id=tenant.tenant_id)
    response_items: list[DataspaceConnectorResponse] = []
    for connector in connectors:
        refs = await service.get_connector_secret_refs(
            tenant_id=tenant.tenant_id,
            connector_id=connector.id,
        )
        response_items.append(_connector_response(connector, secret_refs=refs))
    return DataspaceConnectorListResponse(connectors=response_items, count=len(response_items))


@router.patch(
    "/connectors/{connector_id}",
    response_model=DataspaceConnectorResponse,
)
async def update_dataspace_connector(
    connector_id: UUID,
    body: DataspaceConnectorUpdateRequest,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> DataspaceConnectorResponse:
    """Patch a dataspace connector."""
    service = DataspaceService(db)
    connector = await service.get_connector(
        tenant_id=tenant.tenant_id,
        connector_id=connector_id,
    )
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataspace connector {connector_id} not found",
        )

    await require_access(
        tenant.user,
        "update",
        build_connector_resource_context(connector),
        tenant=tenant,
    )

    try:
        connector, secret_refs = await service.update_connector(
            tenant_id=tenant.tenant_id,
            connector_id=connector_id,
            body=body,
        )
    except DataspaceServiceError as exc:
        raise _as_http_error(exc) from exc

    await db.commit()

    await emit_audit_event(
        db_session=db,
        action="update_dataspace_connector",
        resource_type="dataspace_connector",
        resource_id=str(connector.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
    )

    return _connector_response(connector, secret_refs=secret_refs)


@router.post(
    "/connectors/{connector_id}/validate",
    response_model=ConnectorValidationResponse,
)
async def validate_dataspace_connector(
    connector_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> ConnectorValidationResponse:
    """Validate dataspace connector runtime readiness."""
    service = DataspaceService(db)
    connector = await service.get_connector(
        tenant_id=tenant.tenant_id,
        connector_id=connector_id,
    )
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataspace connector {connector_id} not found",
        )

    await require_access(
        tenant.user,
        "test",
        build_connector_resource_context(connector),
        tenant=tenant,
    )

    try:
        result = await service.validate_connector(
            tenant_id=tenant.tenant_id,
            connector_id=connector_id,
        )
    except DataspaceServiceError as exc:
        raise _as_http_error(exc) from exc

    await db.commit()

    await emit_audit_event(
        db_session=db,
        action="validate_dataspace_connector",
        resource_type="dataspace_connector",
        resource_id=str(connector_id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"status": result.get("status", "error")},
    )

    errors: list[str] = []
    if result.get("status") != "ok" and result.get("error_message"):
        errors.append(str(result["error_message"]))

    return ConnectorValidationResponse(
        status="ok" if result.get("status") == "ok" else "error",
        details=result,
        errors=errors,
    )


@router.get(
    "/connectors/{connector_id}/assets",
    response_model=AssetPublicationListResponse,
)
async def list_connector_assets(
    connector_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> AssetPublicationListResponse:
    """List published dataspace assets for a connector."""
    service = DataspaceService(db)
    connector = await service.get_connector(
        tenant_id=tenant.tenant_id,
        connector_id=connector_id,
    )
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataspace connector {connector_id} not found",
        )
    await require_access(
        tenant.user,
        "read",
        build_connector_resource_context(connector),
        tenant=tenant,
    )
    rows = await service.list_publications(
        tenant_id=tenant.tenant_id,
        connector_id=connector_id,
    )
    items = [_asset_publication_response(row) for row in rows]
    return AssetPublicationListResponse(items=items, count=len(items))


@router.get(
    "/connectors/{connector_id}/negotiations",
    response_model=NegotiationListResponse,
)
async def list_connector_negotiations(
    connector_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> NegotiationListResponse:
    """List dataspace negotiations for a connector."""
    service = DataspaceService(db)
    connector = await service.get_connector(
        tenant_id=tenant.tenant_id,
        connector_id=connector_id,
    )
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataspace connector {connector_id} not found",
        )
    await require_access(
        tenant.user,
        "read",
        build_connector_resource_context(connector),
        tenant=tenant,
    )
    rows = await service.list_negotiations(
        tenant_id=tenant.tenant_id,
        connector_id=connector_id,
    )
    items = [_negotiation_response(row) for row in rows]
    return NegotiationListResponse(items=items, count=len(items))


@router.get(
    "/connectors/{connector_id}/transfers",
    response_model=TransferListResponse,
)
async def list_connector_transfers(
    connector_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> TransferListResponse:
    """List dataspace transfers for a connector."""
    service = DataspaceService(db)
    connector = await service.get_connector(
        tenant_id=tenant.tenant_id,
        connector_id=connector_id,
    )
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataspace connector {connector_id} not found",
        )
    await require_access(
        tenant.user,
        "read",
        build_connector_resource_context(connector),
        tenant=tenant,
    )
    rows = await service.list_transfers(
        tenant_id=tenant.tenant_id,
        connector_id=connector_id,
    )
    items = [_transfer_response(row) for row in rows]
    return TransferListResponse(items=items, count=len(items))


@router.get(
    "/connectors/{connector_id}/conformance-runs",
    response_model=ConformanceRunListResponse,
)
async def list_connector_conformance_runs(
    connector_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> ConformanceRunListResponse:
    """List conformance run history for a connector."""
    service = DataspaceService(db)
    connector = await service.get_connector(
        tenant_id=tenant.tenant_id,
        connector_id=connector_id,
    )
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataspace connector {connector_id} not found",
        )
    await require_access(
        tenant.user,
        "read",
        build_connector_resource_context(connector),
        tenant=tenant,
    )
    rows = await service.list_conformance_runs(
        tenant_id=tenant.tenant_id,
        connector_id=connector_id,
    )
    items = [ConformanceRunResponse.model_validate(row) for row in rows]
    return ConformanceRunListResponse(items=items, count=len(items))


@router.get("/policy-templates", response_model=PolicyTemplateListResponse)
async def list_policy_templates(
    db: DbSession,
    tenant: TenantPublisher,
) -> PolicyTemplateListResponse:
    """List dataspace policy templates for this tenant."""
    await require_access(tenant.user, "list", {"type": "connector"}, tenant=tenant)
    service = DataspaceService(db)
    templates = await service.list_policy_templates(tenant_id=tenant.tenant_id)
    response_items = [_policy_template_response(item) for item in templates]
    return PolicyTemplateListResponse(templates=response_items, count=len(response_items))


@router.post(
    "/policy-templates",
    response_model=PolicyTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_policy_template(
    body: PolicyTemplateCreateRequest,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> PolicyTemplateResponse:
    """Create a draft dataspace policy template."""
    await require_access(tenant.user, "create", {"type": "connector"}, tenant=tenant)
    service = DataspaceService(db)
    try:
        template = await service.create_policy_template(
            tenant_id=tenant.tenant_id,
            body=body,
            created_by_subject=tenant.user.sub,
        )
    except DataspaceServiceError as exc:
        raise _as_http_error(exc) from exc
    await db.commit()

    await emit_audit_event(
        db_session=db,
        action="create_dataspace_policy_template",
        resource_type="dataspace_policy_template",
        resource_id=str(template.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"state": template.state.value},
    )
    return _policy_template_response(template)


@router.patch("/policy-templates/{policy_template_id}", response_model=PolicyTemplateResponse)
async def update_policy_template(
    policy_template_id: UUID,
    body: PolicyTemplateUpdateRequest,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> PolicyTemplateResponse:
    """Update a draft dataspace policy template."""
    await require_access(tenant.user, "update", {"type": "connector"}, tenant=tenant)
    service = DataspaceService(db)
    try:
        template = await service.update_policy_template(
            tenant_id=tenant.tenant_id,
            policy_template_id=policy_template_id,
            body=body,
        )
    except DataspaceServiceError as exc:
        raise _as_http_error(exc) from exc
    await db.commit()

    await emit_audit_event(
        db_session=db,
        action="update_dataspace_policy_template",
        resource_type="dataspace_policy_template",
        resource_id=str(template.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"state": template.state.value},
    )
    return _policy_template_response(template)


@router.post(
    "/policy-templates/{policy_template_id}/approve", response_model=PolicyTemplateResponse
)
async def approve_policy_template(
    policy_template_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> PolicyTemplateResponse:
    """Approve a draft policy template."""
    await require_access(tenant.user, "update", {"type": "connector"}, tenant=tenant)
    service = DataspaceService(db)
    try:
        template = await service.transition_policy_template(
            tenant_id=tenant.tenant_id,
            policy_template_id=policy_template_id,
            to_state=DataspacePolicyTemplateState.APPROVED,
            actor_subject=tenant.user.sub,
        )
    except DataspaceServiceError as exc:
        raise _as_http_error(exc) from exc
    await db.commit()
    await emit_audit_event(
        db_session=db,
        action="approve_dataspace_policy_template",
        resource_type="dataspace_policy_template",
        resource_id=str(template.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"state": template.state.value},
    )
    return _policy_template_response(template)


@router.post(
    "/policy-templates/{policy_template_id}/activate", response_model=PolicyTemplateResponse
)
async def activate_policy_template(
    policy_template_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> PolicyTemplateResponse:
    """Activate an approved policy template."""
    await require_access(tenant.user, "update", {"type": "connector"}, tenant=tenant)
    service = DataspaceService(db)
    try:
        template = await service.transition_policy_template(
            tenant_id=tenant.tenant_id,
            policy_template_id=policy_template_id,
            to_state=DataspacePolicyTemplateState.ACTIVE,
            actor_subject=tenant.user.sub,
        )
    except DataspaceServiceError as exc:
        raise _as_http_error(exc) from exc
    await db.commit()
    await emit_audit_event(
        db_session=db,
        action="activate_dataspace_policy_template",
        resource_type="dataspace_policy_template",
        resource_id=str(template.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"state": template.state.value},
    )
    return _policy_template_response(template)


@router.post(
    "/policy-templates/{policy_template_id}/supersede",
    response_model=PolicyTemplateResponse,
)
async def supersede_policy_template(
    policy_template_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> PolicyTemplateResponse:
    """Supersede an approved or active policy template."""
    await require_access(tenant.user, "update", {"type": "connector"}, tenant=tenant)
    service = DataspaceService(db)
    try:
        template = await service.transition_policy_template(
            tenant_id=tenant.tenant_id,
            policy_template_id=policy_template_id,
            to_state=DataspacePolicyTemplateState.SUPERSEDED,
            actor_subject=tenant.user.sub,
        )
    except DataspaceServiceError as exc:
        raise _as_http_error(exc) from exc
    await db.commit()
    await emit_audit_event(
        db_session=db,
        action="supersede_dataspace_policy_template",
        resource_type="dataspace_policy_template",
        resource_id=str(template.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"state": template.state.value},
    )
    return _policy_template_response(template)


@router.post("/assets/publish", response_model=AssetPublicationResponse)
async def publish_dataspace_asset(
    body: AssetPublishRequest,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> AssetPublicationResponse:
    """Publish a DPP as a dataspace asset."""
    dpp_service = DPPService(db)
    dpp = await dpp_service.get_dpp(body.dpp_id, tenant.tenant_id)
    if dpp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {body.dpp_id} not found",
        )

    await require_access(
        tenant.user,
        "publish_to_connector",
        build_dpp_resource_context(dpp),
        tenant=tenant,
    )

    service = DataspaceService(db)
    try:
        publication = await service.publish_asset(
            tenant_id=tenant.tenant_id,
            body=body,
            created_by_subject=tenant.user.sub,
        )
    except DataspaceServiceError as exc:
        raise _as_http_error(exc) from exc

    await db.commit()

    await emit_audit_event(
        db_session=db,
        action="publish_dataspace_asset",
        resource_type="dataspace_asset_publication",
        resource_id=str(publication.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={
            "connector_id": str(publication.connector_id),
            "asset_id": publication.asset_id,
        },
    )

    return AssetPublicationResponse(
        id=publication.id,
        status=publication.status,
        dpp_id=publication.dpp_id,
        connector_id=publication.connector_id,
        asset_id=publication.asset_id,
        access_policy_id=publication.access_policy_id,
        usage_policy_id=publication.usage_policy_id,
        contract_definition_id=publication.contract_definition_id,
        created_at=publication.created_at,
        updated_at=publication.updated_at,
    )


@router.post("/catalog/query", response_model=CatalogQueryResponse)
async def query_dataspace_catalog(
    body: CatalogQueryRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> CatalogQueryResponse:
    """Query a remote dataspace catalog through the configured connector runtime."""
    service = DataspaceService(db)
    connector = await service.get_connector(
        tenant_id=tenant.tenant_id,
        connector_id=body.connector_id,
    )
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataspace connector {body.connector_id} not found",
        )

    await require_access(
        tenant.user,
        "read",
        build_connector_resource_context(connector),
        tenant=tenant,
    )

    try:
        raw = await service.query_catalog(
            tenant_id=tenant.tenant_id,
            connector_id=body.connector_id,
            connector_address=body.connector_address,
            protocol=body.protocol,
            query_spec=body.query_spec,
        )
    except DataspaceServiceError as exc:
        return CatalogQueryResponse(status="error", error_message=str(exc))

    return CatalogQueryResponse(status="ok", entries=_catalog_entries(raw), raw=raw)


@router.post("/negotiations", response_model=NegotiationResponse)
async def create_negotiation(
    body: NegotiationCreateRequest,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> NegotiationResponse:
    """Start a dataspace contract negotiation."""
    service = DataspaceService(db)
    connector = await service.get_connector(
        tenant_id=tenant.tenant_id,
        connector_id=body.connector_id,
    )
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataspace connector {body.connector_id} not found",
        )
    await require_access(
        tenant.user,
        "update",
        build_connector_resource_context(connector),
        tenant=tenant,
    )

    try:
        negotiation = await service.create_negotiation(
            tenant_id=tenant.tenant_id,
            body=body,
            created_by_subject=tenant.user.sub,
        )
    except DataspaceServiceError as exc:
        raise _as_http_error(exc) from exc

    await db.commit()

    await emit_audit_event(
        db_session=db,
        action="create_dataspace_negotiation",
        resource_type="dataspace_negotiation",
        resource_id=str(negotiation.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"state": negotiation.state},
    )

    return _negotiation_response(negotiation)


@router.get("/negotiations/{negotiation_id}", response_model=NegotiationResponse)
async def get_negotiation(
    negotiation_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> NegotiationResponse:
    """Get and refresh negotiation state from runtime."""
    service = DataspaceService(db)
    negotiation = await service.get_negotiation(
        tenant_id=tenant.tenant_id,
        negotiation_id=negotiation_id,
    )
    if negotiation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Negotiation {negotiation_id} not found",
        )

    connector = await service.get_connector(
        tenant_id=tenant.tenant_id,
        connector_id=negotiation.connector_id,
    )
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataspace connector {negotiation.connector_id} not found",
        )
    await require_access(
        tenant.user,
        "read",
        build_connector_resource_context(connector),
        tenant=tenant,
    )

    try:
        negotiation = await service.refresh_negotiation(
            tenant_id=tenant.tenant_id,
            negotiation_id=negotiation_id,
        )
    except DataspaceServiceError as exc:
        raise _as_http_error(exc) from exc
    await db.commit()

    return NegotiationResponse(
        id=negotiation.id,
        connector_id=negotiation.connector_id,
        publication_id=negotiation.publication_id,
        negotiation_id=negotiation.negotiation_id,
        state=negotiation.state,
        contract_agreement_id=negotiation.contract_agreement_id,
        created_at=negotiation.created_at,
        updated_at=negotiation.updated_at,
    )


@router.post("/transfers", response_model=TransferResponse)
async def create_transfer(
    body: TransferCreateRequest,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> TransferResponse:
    """Start a dataspace transfer process."""
    service = DataspaceService(db)
    connector = await service.get_connector(
        tenant_id=tenant.tenant_id,
        connector_id=body.connector_id,
    )
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataspace connector {body.connector_id} not found",
        )

    await require_access(
        tenant.user,
        "update",
        build_connector_resource_context(connector),
        tenant=tenant,
    )

    try:
        transfer = await service.create_transfer(
            tenant_id=tenant.tenant_id,
            body=body,
            created_by_subject=tenant.user.sub,
        )
    except DataspaceServiceError as exc:
        raise _as_http_error(exc) from exc

    await db.commit()

    await emit_audit_event(
        db_session=db,
        action="create_dataspace_transfer",
        resource_type="dataspace_transfer",
        resource_id=str(transfer.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"state": transfer.state},
    )

    return _transfer_response(transfer)


@router.get("/transfers/{transfer_id}", response_model=TransferResponse)
async def get_transfer(
    transfer_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> TransferResponse:
    """Get and refresh transfer process state from runtime."""
    service = DataspaceService(db)
    transfer = await service.get_transfer(
        tenant_id=tenant.tenant_id,
        transfer_id=transfer_id,
    )
    if transfer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transfer {transfer_id} not found",
        )
    connector = await service.get_connector(
        tenant_id=tenant.tenant_id,
        connector_id=transfer.connector_id,
    )
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataspace connector {transfer.connector_id} not found",
        )
    await require_access(
        tenant.user,
        "read",
        build_connector_resource_context(connector),
        tenant=tenant,
    )

    try:
        transfer = await service.refresh_transfer(
            tenant_id=tenant.tenant_id,
            transfer_id=transfer_id,
        )
    except DataspaceServiceError as exc:
        raise _as_http_error(exc) from exc
    await db.commit()

    return _transfer_response(transfer)


@router.post("/conformance/dsp-tck/runs", response_model=ConformanceRunResponse)
async def create_dsp_tck_run(
    body: ConformanceRunRequest,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> ConformanceRunResponse:
    """Run and persist DSP-TCK conformance metadata."""
    if body.connector_id:
        service = DataspaceService(db)
        connector = await service.get_connector(
            tenant_id=tenant.tenant_id,
            connector_id=body.connector_id,
        )
        if connector is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataspace connector {body.connector_id} not found",
            )
        await require_access(
            tenant.user,
            "update",
            build_connector_resource_context(connector),
            tenant=tenant,
        )
    else:
        await require_access(tenant.user, "create", {"type": "connector"}, tenant=tenant)
        service = DataspaceService(db)

    run = await service.create_conformance_run(
        tenant_id=tenant.tenant_id,
        connector_id=body.connector_id,
        profile=body.profile,
        metadata=body.metadata,
        created_by_subject=tenant.user.sub,
    )
    await db.commit()

    await emit_audit_event(
        db_session=db,
        action="create_dataspace_conformance_run",
        resource_type="dataspace_conformance_run",
        resource_id=str(run.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"status": run.status.value, "profile": run.run_type},
    )

    return ConformanceRunResponse.model_validate(run)


@router.get("/conformance/dsp-tck/runs/{run_id}", response_model=ConformanceRunResponse)
async def get_dsp_tck_run(
    run_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> ConformanceRunResponse:
    """Read a persisted DSP-TCK conformance run result."""
    service = DataspaceService(db)
    run = await service.get_conformance_run(tenant_id=tenant.tenant_id, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {run_id} not found")
    if run.connector_id is None:
        await require_access(tenant.user, "read", {"type": "connector"}, tenant=tenant)
    else:
        connector = await service.get_connector(
            tenant_id=tenant.tenant_id,
            connector_id=run.connector_id,
        )
        if connector is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataspace connector {run.connector_id} not found",
            )
        await require_access(
            tenant.user,
            "read",
            build_connector_resource_context(connector),
            tenant=tenant,
        )
    return ConformanceRunResponse.model_validate(run)


@router.get("/evidence/dpps/{dpp_id}", response_model=RegulatoryEvidenceResponse)
async def get_dpp_regulatory_evidence(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
    profile: str = "espr_core",
) -> RegulatoryEvidenceResponse:
    """Return aggregated regulatory and dataspace evidence for a DPP."""
    dpp_service = DPPService(db)
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
    if dpp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"DPP {dpp_id} not found")
    await require_access(
        tenant.user,
        "read",
        build_dpp_resource_context(dpp),
        tenant=tenant,
    )

    service = DataspaceService(db)
    return await service.build_regulatory_evidence(
        tenant_id=tenant.tenant_id,
        dpp_id=dpp_id,
        profile=profile,
    )


@router.post("/manifests:diff", response_model=ManifestDiffResponse)
async def diff_manifest(
    body: ConnectorManifest,
    db: DbSession,
    tenant: TenantPublisher,
) -> ManifestDiffResponse:
    """Preview config-as-code changes for connector manifests."""
    await require_access(tenant.user, "create", {"type": "connector"}, tenant=tenant)
    service = DataspaceService(db)
    changes = await service.diff_manifest(tenant_id=tenant.tenant_id, manifest=body)
    return ManifestDiffResponse(has_changes=len(changes) > 0, changes=changes)


@router.post("/manifests:apply", response_model=ManifestApplyResponse)
async def apply_manifest(
    body: ConnectorManifest,
    request: Request,
    response: Response,
    db: DbSession,
    tenant: TenantPublisher,
) -> ManifestApplyResponse:
    """Apply config-as-code manifest to connector and policy-template resources."""
    await require_access(tenant.user, "create", {"type": "connector"}, tenant=tenant)
    service = DataspaceService(db)
    connector, changes = await service.apply_manifest(
        tenant_id=tenant.tenant_id,
        manifest=body,
        created_by_subject=tenant.user.sub,
    )
    await db.commit()

    await emit_audit_event(
        db_session=db,
        action="apply_dataspace_manifest",
        resource_type="dataspace_connector",
        resource_id=str(connector.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"change_count": len(changes)},
    )

    response.status_code = status.HTTP_200_OK
    return ManifestApplyResponse(
        status="applied" if changes else "noop",
        connector_id=connector.id,
        applied_changes=changes,
    )
