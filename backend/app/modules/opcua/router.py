"""API router for OPC UA sources, nodesets, and mappings.

Provides 19 CRUD + utility endpoints mounted at
``{tenant_prefix}/opcua``.  All endpoints require the ``publisher`` role
and are gated behind the ``opcua_enabled`` feature flag.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)

from app.core.audit import emit_audit_event
from app.core.config import get_settings
from app.core.security import require_access
from app.core.security.resource_context import (
    build_dpp_resource_context,
    build_opcua_mapping_resource_context,
    build_opcua_nodeset_resource_context,
    build_opcua_source_resource_context,
)
from app.core.tenancy import TenantPublisher
from app.db.models import OPCUAMapping, OPCUAMappingType, OPCUANodeSet, OPCUASource
from app.db.session import DbSession
from app.modules.webhooks.service import trigger_webhooks

from .schemas import (
    DataspacePublicationJobListResponse,
    DataspacePublicationJobResponse,
    DataspacePublishRequest,
    DryRunRequest,
    MappingDryRunResult,
    MappingValidationResult,
    NodeSearchResult,
    OPCUAMappingCreate,
    OPCUAMappingListResponse,
    OPCUAMappingResponse,
    OPCUAMappingUpdate,
    OPCUANodeSetDetailResponse,
    OPCUANodeSetListResponse,
    OPCUANodeSetResponse,
    OPCUANodeSetUploadMeta,
    OPCUASourceCreate,
    OPCUASourceListResponse,
    OPCUASourceResponse,
    OPCUASourceUpdate,
    TestConnectionResult,
)
from .service import (
    MappingService,
    NodeSetService,
    NodeSetStorageError,
    OPCUASourceService,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Feature flag gate
# ---------------------------------------------------------------------------


def _require_opcua_enabled() -> None:
    """Raise 410 Gone if OPC UA feature is disabled."""
    if not get_settings().opcua_enabled:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="OPC UA feature is not enabled",
        )


# ---------------------------------------------------------------------------
# ABAC resource helpers
# ---------------------------------------------------------------------------


async def _get_source_or_404(
    source_id: UUID,
    tenant: TenantPublisher,
    db: DbSession,
    request: Request,
    *,
    action: str = "read",
) -> OPCUASource:
    """Load an OPC UA source and check ABAC access."""
    svc = OPCUASourceService(db)
    source = await svc.get_source(source_id, tenant.tenant_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OPC UA source {source_id} not found",
        )
    await require_access(
        tenant.user,
        action,
        build_opcua_source_resource_context(source),
        request=request,
        tenant=tenant,
    )
    return source


async def _get_nodeset_or_404(
    nodeset_id: UUID,
    tenant: TenantPublisher,
    db: DbSession,
    request: Request,
    *,
    action: str = "read",
) -> OPCUANodeSet:
    """Load an OPC UA nodeset and check ABAC access."""
    svc = NodeSetService(db)
    nodeset = await svc.get_nodeset(nodeset_id, tenant.tenant_id)
    if not nodeset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OPC UA nodeset {nodeset_id} not found",
        )
    await require_access(
        tenant.user,
        action,
        build_opcua_nodeset_resource_context(nodeset),
        request=request,
        tenant=tenant,
    )
    return nodeset


async def _get_mapping_or_404(
    mapping_id: UUID,
    tenant: TenantPublisher,
    db: DbSession,
    request: Request,
    *,
    action: str = "read",
) -> OPCUAMapping:
    """Load an OPC UA mapping and check ABAC access."""
    svc = MappingService(db)
    mapping = await svc.get_mapping(mapping_id, tenant.tenant_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OPC UA mapping {mapping_id} not found",
        )
    await require_access(
        tenant.user,
        action,
        build_opcua_mapping_resource_context(mapping),
        request=request,
        tenant=tenant,
    )
    return mapping


async def _get_dpp_or_404(
    dpp_id: UUID,
    tenant: TenantPublisher,
    db: DbSession,
    *,
    action: str = "read",
    request: Request | None = None,
) -> object:
    """Load a DPP and check ABAC access for the requested action."""
    from app.modules.dpps.service import DPPService

    svc = DPPService(db)
    dpp = await svc.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )
    shared_with_current_user = await svc.is_resource_shared_with_user(
        tenant_id=tenant.tenant_id,
        resource_type="dpp",
        resource_id=dpp.id,
        user_subject=tenant.user.sub,
    )
    await require_access(
        tenant.user,
        action,
        build_dpp_resource_context(dpp, shared_with_current_user=shared_with_current_user),
        request=request,
        tenant=tenant,
    )
    return dpp


def _source_to_response(source: OPCUASource) -> OPCUASourceResponse:
    """Convert an OPCUASource ORM model to a response, computing ``has_password``."""
    resp = OPCUASourceResponse.model_validate(source)
    resp.has_password = bool(source.password_encrypted)
    return resp


# ==========================================================================
# OPC UA Source endpoints (6)
# ==========================================================================


@router.get("/sources", response_model=OPCUASourceListResponse)
async def list_sources(
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> OPCUASourceListResponse:
    """List OPC UA sources for the current tenant."""
    _require_opcua_enabled()
    await require_access(
        tenant.user,
        "list",
        {"type": "opcua_source", "tenant_id": str(tenant.tenant_id)},
        request=request,
        tenant=tenant,
    )
    svc = OPCUASourceService(db)
    items, total = await svc.list_sources(tenant.tenant_id, offset=offset, limit=limit)
    return OPCUASourceListResponse(
        items=[_source_to_response(s) for s in items],
        total=total,
    )


@router.post(
    "/sources",
    response_model=OPCUASourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_source(
    data: OPCUASourceCreate,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> OPCUASourceResponse:
    """Register a new OPC UA source."""
    _require_opcua_enabled()
    await require_access(
        tenant.user,
        "create",
        {"type": "opcua_source", "tenant_id": str(tenant.tenant_id)},
        request=request,
        tenant=tenant,
    )
    svc = OPCUASourceService(db)
    source = await svc.create_source(tenant.tenant_id, data, tenant.user.sub)

    await emit_audit_event(
        db_session=db,
        action="opcua_source_create",
        resource_type="opcua_source",
        resource_id=source.id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        metadata={"name": source.name, "endpoint_url": source.endpoint_url},
    )
    await trigger_webhooks(
        db,
        tenant.tenant_id,
        "opcua_source.created",
        {"source_id": str(source.id), "name": source.name},
    )
    return _source_to_response(source)


@router.get("/sources/{source_id}", response_model=OPCUASourceResponse)
async def get_source(
    source_id: UUID,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> OPCUASourceResponse:
    """Get details of a single OPC UA source (password never exposed)."""
    _require_opcua_enabled()
    source = await _get_source_or_404(source_id, tenant, db, request, action="read")
    return _source_to_response(source)


@router.patch("/sources/{source_id}", response_model=OPCUASourceResponse)
async def update_source(
    source_id: UUID,
    data: OPCUASourceUpdate,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> OPCUASourceResponse:
    """Update an existing OPC UA source."""
    _require_opcua_enabled()
    source = await _get_source_or_404(source_id, tenant, db, request, action="update")
    svc = OPCUASourceService(db)
    updated = await svc.update_source(source, data)

    await emit_audit_event(
        db_session=db,
        action="opcua_source_update",
        resource_type="opcua_source",
        resource_id=updated.id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
    )
    return _source_to_response(updated)


@router.delete(
    "/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_source(
    source_id: UUID,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> None:
    """Delete an OPC UA source and all related nodesets/mappings."""
    _require_opcua_enabled()
    source = await _get_source_or_404(source_id, tenant, db, request, action="delete")
    svc = OPCUASourceService(db)
    await svc.delete_source(source)

    await emit_audit_event(
        db_session=db,
        action="opcua_source_delete",
        resource_type="opcua_source",
        resource_id=source_id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
    )
    await trigger_webhooks(
        db,
        tenant.tenant_id,
        "opcua_source.deleted",
        {"source_id": str(source_id)},
    )


@router.post(
    "/sources/{source_id}/test-connection",
    response_model=TestConnectionResult,
)
async def test_connection(
    source_id: UUID,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> TestConnectionResult:
    """Test connectivity to an OPC UA endpoint (3s timeout)."""
    _require_opcua_enabled()
    source = await _get_source_or_404(source_id, tenant, db, request, action="test")
    svc = OPCUASourceService(db)
    return await svc.test_connection(source)


# ==========================================================================
# OPC UA NodeSet endpoints (6)
# ==========================================================================


@router.get("/nodesets", response_model=OPCUANodeSetListResponse)
async def list_nodesets(
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
    source_id: UUID | None = Query(default=None, alias="sourceId"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> OPCUANodeSetListResponse:
    """List uploaded NodeSets, optionally filtered by source."""
    _require_opcua_enabled()
    await require_access(
        tenant.user,
        "list",
        {"type": "opcua_nodeset", "tenant_id": str(tenant.tenant_id)},
        request=request,
        tenant=tenant,
    )
    svc = NodeSetService(db)
    items, total = await svc.list_nodesets(
        tenant.tenant_id, source_id=source_id, offset=offset, limit=limit
    )
    return OPCUANodeSetListResponse(
        items=[_nodeset_to_response(ns) for ns in items],
        total=total,
    )


@router.post(
    "/nodesets/upload",
    response_model=OPCUANodeSetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_nodeset(
    xml_file: UploadFile = File(..., description="NodeSet2.xml file"),
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
    source_id: UUID | None = Query(default=None, alias="sourceId"),
    companion_spec_name: str | None = Query(default=None, alias="companionSpecName"),
    companion_spec_version: str | None = Query(default=None, alias="companionSpecVersion"),
) -> OPCUANodeSetResponse:
    """Upload a NodeSet2.xml, parse it, and store metadata + file."""
    _require_opcua_enabled()
    await require_access(
        tenant.user,
        "create",
        {"type": "opcua_nodeset", "tenant_id": str(tenant.tenant_id)},
        request=request,
        tenant=tenant,
    )

    xml_bytes = await xml_file.read()
    if not xml_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded XML file is empty",
        )

    max_size = get_settings().opcua_nodeset_max_upload_bytes
    if len(xml_bytes) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"NodeSet XML exceeds maximum upload size of {max_size} bytes",
        )

    meta = OPCUANodeSetUploadMeta(
        source_id=source_id,
        companion_spec_name=companion_spec_name,
        companion_spec_version=companion_spec_version,
    )

    svc = NodeSetService(db)
    try:
        nodeset = await svc.upload(
            tenant.tenant_id,
            xml_bytes,
            meta,
            tenant.user.sub,
        )
    except NodeSetStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse NodeSet XML: {type(exc).__name__}",
        ) from exc

    await emit_audit_event(
        db_session=db,
        action="opcua_nodeset_upload",
        resource_type="opcua_nodeset",
        resource_id=nodeset.id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        metadata={"namespace_uri": nodeset.namespace_uri},
    )
    return _nodeset_to_response(nodeset)


@router.get("/nodesets/{nodeset_id}", response_model=OPCUANodeSetDetailResponse)
async def get_nodeset(
    nodeset_id: UUID,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> OPCUANodeSetDetailResponse:
    """Get full detail of a NodeSet including parsed node graph."""
    _require_opcua_enabled()
    nodeset = await _get_nodeset_or_404(nodeset_id, tenant, db, request, action="read")
    resp = OPCUANodeSetDetailResponse.model_validate(nodeset)
    resp.node_count = (nodeset.parsed_summary_json or {}).get("total_nodes", 0)
    return resp


@router.get("/nodesets/{nodeset_id}/download")
async def download_nodeset(
    nodeset_id: UUID,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> dict[str, str]:
    """Generate a presigned download URL for the NodeSet XML."""
    _require_opcua_enabled()
    nodeset = await _get_nodeset_or_404(nodeset_id, tenant, db, request, action="download")
    svc = NodeSetService(db)
    try:
        download_url = svc.generate_download_url(nodeset)
    except NodeSetStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return {"download_url": download_url}


@router.get("/nodesets/{nodeset_id}/nodes", response_model=list[NodeSearchResult])
async def search_nodeset_nodes(
    nodeset_id: UUID,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
    q: str = Query(..., min_length=1, description="Search query"),
    node_class: str | None = Query(default=None, alias="nodeClass"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[NodeSearchResult]:
    """Search the parsed node graph of a NodeSet."""
    _require_opcua_enabled()
    nodeset = await _get_nodeset_or_404(nodeset_id, tenant, db, request, action="read")
    results = NodeSetService.search_nodes(nodeset, query=q, node_class=node_class, limit=limit)
    return [NodeSearchResult(**r) for r in results]


@router.delete(
    "/nodesets/{nodeset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_nodeset(
    nodeset_id: UUID,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> None:
    """Delete a NodeSet from DB and object storage."""
    _require_opcua_enabled()
    nodeset = await _get_nodeset_or_404(nodeset_id, tenant, db, request, action="delete")
    svc = NodeSetService(db)
    await svc.delete_nodeset(nodeset)

    await emit_audit_event(
        db_session=db,
        action="opcua_nodeset_delete",
        resource_type="opcua_nodeset",
        resource_id=nodeset_id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
    )


# ==========================================================================
# OPC UA Mapping endpoints (7)
# ==========================================================================


@router.get("/mappings", response_model=OPCUAMappingListResponse)
async def list_mappings(
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
    source_id: UUID | None = Query(default=None, alias="sourceId"),
    mapping_type: OPCUAMappingType | None = Query(default=None, alias="mappingType"),
    is_enabled: bool | None = Query(default=None, alias="isEnabled"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> OPCUAMappingListResponse:
    """List OPC UA mappings with optional filters."""
    _require_opcua_enabled()
    await require_access(
        tenant.user,
        "list",
        {"type": "opcua_mapping", "tenant_id": str(tenant.tenant_id)},
        request=request,
        tenant=tenant,
    )
    svc = MappingService(db)
    items, total = await svc.list_mappings(
        tenant.tenant_id,
        source_id=source_id,
        mapping_type=mapping_type,
        is_enabled=is_enabled,
        offset=offset,
        limit=limit,
    )
    return OPCUAMappingListResponse(
        items=[OPCUAMappingResponse.model_validate(m) for m in items],
        total=total,
    )


@router.post(
    "/mappings",
    response_model=OPCUAMappingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_mapping(
    data: OPCUAMappingCreate,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> OPCUAMappingResponse:
    """Create a new OPC UA → AAS/EPCIS mapping."""
    _require_opcua_enabled()
    await require_access(
        tenant.user,
        "create",
        {"type": "opcua_mapping", "tenant_id": str(tenant.tenant_id)},
        request=request,
        tenant=tenant,
    )
    await _get_source_or_404(data.source_id, tenant, db, request, action="read")
    if data.nodeset_id is not None:
        await _get_nodeset_or_404(data.nodeset_id, tenant, db, request, action="read")
    if data.dpp_id is not None:
        await _get_dpp_or_404(data.dpp_id, tenant, db, action="read", request=request)

    # Validate transform expression at creation time
    if data.value_transform_expr:
        from .transform import validate_transform_expr

        errors = validate_transform_expr(data.value_transform_expr)
        if errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid transform expression: {'; '.join(errors)}",
            )

    svc = MappingService(db)
    mapping = await svc.create_mapping(tenant.tenant_id, data, tenant.user.sub)

    await emit_audit_event(
        db_session=db,
        action="opcua_mapping_create",
        resource_type="opcua_mapping",
        resource_id=mapping.id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        metadata={
            "source_id": str(data.source_id),
            "mapping_type": data.mapping_type.value,
        },
    )
    await trigger_webhooks(
        db,
        tenant.tenant_id,
        "opcua_mapping.created",
        {"mapping_id": str(mapping.id), "source_id": str(data.source_id)},
    )
    return OPCUAMappingResponse.model_validate(mapping)


@router.get("/mappings/{mapping_id}", response_model=OPCUAMappingResponse)
async def get_mapping(
    mapping_id: UUID,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> OPCUAMappingResponse:
    """Get details of a single mapping."""
    _require_opcua_enabled()
    mapping = await _get_mapping_or_404(mapping_id, tenant, db, request, action="read")
    return OPCUAMappingResponse.model_validate(mapping)


@router.patch("/mappings/{mapping_id}", response_model=OPCUAMappingResponse)
async def update_mapping(
    mapping_id: UUID,
    data: OPCUAMappingUpdate,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> OPCUAMappingResponse:
    """Update an existing mapping."""
    _require_opcua_enabled()
    mapping = await _get_mapping_or_404(mapping_id, tenant, db, request, action="update")
    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("nodeset_id") is not None:
        await _get_nodeset_or_404(update_data["nodeset_id"], tenant, db, request, action="read")
    if update_data.get("dpp_id") is not None:
        await _get_dpp_or_404(update_data["dpp_id"], tenant, db, action="read", request=request)

    # Re-validate transform expression if changed
    if data.value_transform_expr is not None:
        from .transform import validate_transform_expr

        errors = validate_transform_expr(data.value_transform_expr)
        if errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid transform expression: {'; '.join(errors)}",
            )

    svc = MappingService(db)
    updated = await svc.update_mapping(mapping, data)

    await emit_audit_event(
        db_session=db,
        action="opcua_mapping_update",
        resource_type="opcua_mapping",
        resource_id=updated.id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
    )
    return OPCUAMappingResponse.model_validate(updated)


@router.delete(
    "/mappings/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_mapping(
    mapping_id: UUID,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> None:
    """Delete a mapping."""
    _require_opcua_enabled()
    mapping = await _get_mapping_or_404(mapping_id, tenant, db, request, action="delete")
    svc = MappingService(db)
    await svc.delete_mapping(mapping)

    await emit_audit_event(
        db_session=db,
        action="opcua_mapping_delete",
        resource_type="opcua_mapping",
        resource_id=mapping_id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
    )
    await trigger_webhooks(
        db,
        tenant.tenant_id,
        "opcua_mapping.deleted",
        {"mapping_id": str(mapping_id)},
    )


@router.post(
    "/mappings/{mapping_id}/validate",
    response_model=MappingValidationResult,
)
async def validate_mapping(
    mapping_id: UUID,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> MappingValidationResult:
    """Validate a mapping's NodeId, AAS path, SAMM URN, and transform expression."""
    _require_opcua_enabled()
    mapping = await _get_mapping_or_404(mapping_id, tenant, db, request, action="validate")
    return MappingService.validate_mapping(mapping)


@router.post(
    "/mappings/{mapping_id}/dry-run",
    response_model=MappingDryRunResult,
)
async def dry_run_mapping(
    mapping_id: UUID,
    body: DryRunRequest | None = None,
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> MappingDryRunResult:
    """Preview the effect of a mapping against a DPP revision (no DB writes)."""
    _require_opcua_enabled()
    mapping = await _get_mapping_or_404(mapping_id, tenant, db, request, action="dry_run")
    svc = MappingService(db)
    revision_json = body.revision_json if body else None
    return await svc.dry_run(mapping, revision_json)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _nodeset_to_response(nodeset: OPCUANodeSet) -> OPCUANodeSetResponse:
    """Convert a NodeSet ORM model to a response with computed ``node_count``."""
    resp = OPCUANodeSetResponse.model_validate(nodeset)
    resp.node_count = (nodeset.parsed_summary_json or {}).get("total_nodes", 0)
    return resp


# ==========================================================================
# Dataspace publication endpoints (4)
# ==========================================================================


@router.post(
    "/dataspace/publish",
    response_model=DataspacePublicationJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Queue a DPP for dataspace publication",
)
async def publish_to_dataspace(
    body: DataspacePublishRequest,
    request: Request,
    tenant: TenantPublisher,
    db: DbSession,
) -> DataspacePublicationJobResponse:
    _require_opcua_enabled()
    await _get_dpp_or_404(body.dpp_id, tenant, db, action="publish", request=request)
    from .dataspace import DataspacePublicationService

    ds_svc = DataspacePublicationService(db)
    job = await ds_svc.create_publication_job(
        tenant_id=tenant.tenant_id,
        dpp_id=body.dpp_id,
        target=body.target,
    )
    await emit_audit_event(
        db_session=db,
        action="dataspace.publish.queued",
        resource_type="dataspace_publication_job",
        resource_id=job.id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        metadata={"dpp_id": str(body.dpp_id), "target": body.target},
    )
    return DataspacePublicationJobResponse.model_validate(job)


@router.get(
    "/dataspace/jobs",
    response_model=DataspacePublicationJobListResponse,
    summary="List dataspace publication jobs",
)
async def list_publication_jobs(
    request: Request,
    tenant: TenantPublisher,
    db: DbSession,
    dpp_id: UUID | None = Query(default=None, alias="dppId"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> DataspacePublicationJobListResponse:
    _require_opcua_enabled()
    await require_access(
        tenant.user,
        "list",
        {"type": "dataspace_publication", "tenant_id": str(tenant.tenant_id)},
        request=request,
        tenant=tenant,
    )
    if dpp_id is not None:
        await _get_dpp_or_404(dpp_id, tenant, db, action="read", request=request)

    from app.modules.dpps.service import DPPService

    from .dataspace import DataspacePublicationService

    ds_svc = DataspacePublicationService(db)
    items, total = await ds_svc.list_publication_jobs(
        tenant.tenant_id,
        dpp_id=dpp_id,
        offset=offset,
        limit=limit,
    )

    if dpp_id is None and items:
        dpp_svc = DPPService(db)
        visible_items = []
        access_cache: dict[UUID, bool] = {}
        for job in items:
            allowed = access_cache.get(job.dpp_id)
            if allowed is None:
                dpp = await dpp_svc.get_dpp(job.dpp_id, tenant.tenant_id)
                if dpp is None:
                    access_cache[job.dpp_id] = False
                    continue
                shared_with_current_user = await dpp_svc.is_resource_shared_with_user(
                    tenant_id=tenant.tenant_id,
                    resource_type="dpp",
                    resource_id=dpp.id,
                    user_subject=tenant.user.sub,
                )
                try:
                    await require_access(
                        tenant.user,
                        "read",
                        build_dpp_resource_context(
                            dpp, shared_with_current_user=shared_with_current_user
                        ),
                        request=request,
                        tenant=tenant,
                    )
                    allowed = True
                except HTTPException as exc:
                    if exc.status_code not in {
                        status.HTTP_403_FORBIDDEN,
                        status.HTTP_404_NOT_FOUND,
                    }:
                        raise
                    allowed = False
                access_cache[job.dpp_id] = allowed
            if allowed:
                visible_items.append(job)
        items = visible_items
        total = len(visible_items)

    return DataspacePublicationJobListResponse(
        items=[DataspacePublicationJobResponse.model_validate(j) for j in items],
        total=total,
    )


@router.get(
    "/dataspace/jobs/{job_id}",
    response_model=DataspacePublicationJobResponse,
    summary="Get a publication job",
)
async def get_publication_job(
    job_id: UUID,
    request: Request,
    tenant: TenantPublisher,
    db: DbSession,
) -> DataspacePublicationJobResponse:
    _require_opcua_enabled()
    await require_access(
        tenant.user,
        "read",
        {"type": "dataspace_publication", "tenant_id": str(tenant.tenant_id)},
        request=request,
        tenant=tenant,
    )
    from .dataspace import DataspacePublicationService

    ds_svc = DataspacePublicationService(db)
    job = await ds_svc.get_publication_job(job_id, tenant.tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publication job {job_id} not found",
        )
    await _get_dpp_or_404(job.dpp_id, tenant, db, action="read", request=request)
    return DataspacePublicationJobResponse.model_validate(job)


@router.post(
    "/dataspace/jobs/{job_id}/retry",
    response_model=DataspacePublicationJobResponse,
    summary="Retry a failed publication job",
)
async def retry_publication_job(
    job_id: UUID,
    request: Request,
    tenant: TenantPublisher,
    db: DbSession,
) -> DataspacePublicationJobResponse:
    _require_opcua_enabled()
    await require_access(
        tenant.user,
        "create",
        {"type": "dataspace_publication", "tenant_id": str(tenant.tenant_id)},
        request=request,
        tenant=tenant,
    )
    from .dataspace import DataspacePublicationService

    ds_svc = DataspacePublicationService(db)
    job = await ds_svc.get_publication_job(job_id, tenant.tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publication job {job_id} not found",
        )
    await _get_dpp_or_404(job.dpp_id, tenant, db, action="publish", request=request)
    try:
        job = await ds_svc.retry_publication_job(job)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await emit_audit_event(
        db_session=db,
        action="dataspace.publish.retried",
        resource_type="dataspace_publication_job",
        resource_id=job.id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        metadata={"dpp_id": str(job.dpp_id)},
    )
    return DataspacePublicationJobResponse.model_validate(job)
