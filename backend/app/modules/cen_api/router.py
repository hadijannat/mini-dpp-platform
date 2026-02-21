"""Tenant-scoped CEN prEN 18222 API facade routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.security import require_access
from app.core.security.resource_context import build_dpp_resource_context
from app.core.tenancy import TenantPublisher
from app.db.models import IdentifierEntityType
from app.db.session import DbSession
from app.modules.cen_api.schemas import (
    CENCreateDPPRequest,
    CENDPPResponse,
    CENDPPSearchResponse,
    CENExternalIdentifierResponse,
    CENPaging,
    CENRegisterIdentifierRequest,
    CENSupersedeIdentifierRequest,
    CENSyncResponse,
    CENUpdateDPPRequest,
    CENValidateIdentifierRequest,
    CENValidateIdentifierResponse,
)
from app.modules.cen_api.service import (
    CENAPIConflictError,
    CENAPIError,
    CENAPINotFoundError,
    CENAPIService,
    CENFeatureDisabledError,
)
from app.modules.dpps.service import DPPService
from app.standards.cen_pren import get_cen_profiles, standards_profile_header

router = APIRouter()


def _set_standards_header(response: Response) -> None:
    response.headers["X-Standards-Profile"] = standards_profile_header(get_cen_profiles())


async def _require_dpp_access(
    *,
    db: DbSession,
    tenant: TenantPublisher,
    dpp_id: UUID,
    action: str,
) -> object:
    dpp_service = DPPService(db)
    dpp = await dpp_service.get_dpp(dpp_id=dpp_id, tenant_id=tenant.tenant_id)
    if dpp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DPP not found")
    shared_with_current_user = await dpp_service.is_resource_shared_with_user(
        tenant_id=tenant.tenant_id,
        resource_type="dpp",
        resource_id=dpp.id,
        user_subject=tenant.user.sub,
    )
    await require_access(
        tenant.user,
        action,
        build_dpp_resource_context(dpp, shared_with_current_user=shared_with_current_user),
        tenant=tenant,
    )
    return dpp


@router.post(
    "/dpps",
    response_model=CENDPPResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="CreateDPP",
)
async def create_dpp(
    body: CENCreateDPPRequest,
    db: DbSession,
    tenant: TenantPublisher,
    response: Response,
) -> CENDPPResponse:
    _set_standards_header(response)
    await require_access(tenant.user, "create", {"type": "dpp"}, tenant=tenant)
    service = CENAPIService(db)
    try:
        dpp = await service.create_dpp(
            tenant_id=tenant.tenant_id,
            tenant_slug=tenant.tenant_slug,
            owner_subject=tenant.user.sub,
            asset_ids=body.asset_ids,
            selected_templates=body.selected_templates,
            initial_data=body.initial_data,
            required_specific_asset_ids=body.required_specific_asset_ids,
        )
    except CENAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await db.commit()
    await db.refresh(dpp)
    return await service.to_cen_dpp_response(dpp)


@router.get("/dpps/{dpp_id:uuid}", response_model=CENDPPResponse, operation_id="ReadDPPById")
async def read_dpp_by_id(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
    response: Response,
) -> CENDPPResponse:
    _set_standards_header(response)
    await _require_dpp_access(db=db, tenant=tenant, dpp_id=dpp_id, action="read")
    service = CENAPIService(db)
    try:
        dpp = await service.get_dpp(tenant_id=tenant.tenant_id, dpp_id=dpp_id)
    except CENAPINotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return await service.to_cen_dpp_response(dpp)


@router.get("/dpps", response_model=CENDPPSearchResponse, operation_id="SearchDPPs")
async def search_dpps(
    db: DbSession,
    tenant: TenantPublisher,
    response: Response,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    identifier: str | None = Query(default=None),
    scheme: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
) -> CENDPPSearchResponse:
    _set_standards_header(response)
    await require_access(
        tenant.user,
        "list",
        {"type": "dpp", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = CENAPIService(db)
    try:
        dpps, next_cursor = await service.search_dpps(
            tenant_id=tenant.tenant_id,
            limit=limit,
            cursor=cursor,
            identifier=identifier,
            scheme=scheme,
            status=status_filter,
            user_subject=tenant.user.sub,
            is_tenant_admin=tenant.is_tenant_admin,
        )
    except CENAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return CENDPPSearchResponse(
        items=[await service.to_cen_dpp_response(dpp) for dpp in dpps],
        paging=CENPaging(cursor=next_cursor),
    )


@router.get(
    "/dpps/by-identifier", response_model=CENDPPResponse, operation_id="ReadDPPByIdentifier"
)
async def read_dpp_by_identifier(
    db: DbSession,
    tenant: TenantPublisher,
    response: Response,
    identifier: str = Query(..., min_length=1),
    scheme: str = Query(..., min_length=1),
) -> CENDPPResponse:
    _set_standards_header(response)
    await require_access(
        tenant.user,
        "read",
        {"type": "dpp", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = CENAPIService(db)
    try:
        dpp = await service.read_dpp_by_identifier(
            tenant_id=tenant.tenant_id,
            scheme=scheme,
            identifier=identifier,
            user_subject=tenant.user.sub,
            is_tenant_admin=tenant.is_tenant_admin,
        )
    except CENAPINotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CENAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await _require_dpp_access(db=db, tenant=tenant, dpp_id=dpp.id, action="read")
    return await service.to_cen_dpp_response(dpp)


@router.patch("/dpps/{dpp_id:uuid}", response_model=CENDPPResponse, operation_id="UpdateDPP")
async def update_dpp(
    dpp_id: UUID,
    body: CENUpdateDPPRequest,
    db: DbSession,
    tenant: TenantPublisher,
    response: Response,
) -> CENDPPResponse:
    _set_standards_header(response)
    await _require_dpp_access(db=db, tenant=tenant, dpp_id=dpp_id, action="update")
    service = CENAPIService(db)
    try:
        dpp = await service.update_dpp(
            tenant_id=tenant.tenant_id,
            dpp_id=dpp_id,
            updated_by=tenant.user.sub,
            asset_ids_patch=body.asset_ids,
            visibility_scope=body.visibility_scope,
        )
    except CENAPINotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CENAPIConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CENAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await db.commit()
    await db.refresh(dpp)
    return await service.to_cen_dpp_response(dpp)


@router.delete("/dpps/{dpp_id:uuid}", response_model=CENDPPResponse, operation_id="ArchiveDPP")
async def archive_dpp(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
    response: Response,
) -> CENDPPResponse:
    _set_standards_header(response)
    await _require_dpp_access(db=db, tenant=tenant, dpp_id=dpp_id, action="archive")
    service = CENAPIService(db)
    try:
        dpp = await service.archive_dpp(tenant_id=tenant.tenant_id, dpp_id=dpp_id)
    except CENAPINotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CENAPIConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(dpp)
    return await service.to_cen_dpp_response(dpp)


@router.post(
    "/dpps/{dpp_id:uuid}/publish", response_model=CENDPPResponse, operation_id="PublishDPP"
)
async def publish_dpp(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
    response: Response,
) -> CENDPPResponse:
    _set_standards_header(response)
    await _require_dpp_access(db=db, tenant=tenant, dpp_id=dpp_id, action="publish")
    service = CENAPIService(db)
    try:
        dpp = await service.publish_dpp(
            tenant_id=tenant.tenant_id,
            dpp_id=dpp_id,
            published_by=tenant.user.sub,
        )
    except CENAPINotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CENAPIConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(dpp)
    return await service.to_cen_dpp_response(dpp)


@router.post(
    "/identifiers/validate",
    response_model=CENValidateIdentifierResponse,
    operation_id="ValidateIdentifier",
)
async def validate_identifier(
    body: CENValidateIdentifierRequest,
    db: DbSession,
    tenant: TenantPublisher,
    response: Response,
) -> CENValidateIdentifierResponse:
    _set_standards_header(response)
    await require_access(
        tenant.user,
        "create",
        {"type": "identifier", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = CENAPIService(db)
    try:
        canonical = await service.validate_identifier(
            entity_type=IdentifierEntityType(body.entity_type.value),
            scheme_code=body.scheme_code,
            value_raw=body.value_raw,
            granularity=body.granularity,
        )
    except CENAPIError as exc:
        return CENValidateIdentifierResponse(
            valid=False,
            entity_type=body.entity_type,
            scheme_code=body.scheme_code,
            value_raw=body.value_raw,
            granularity=body.granularity,
            errors=[str(exc)],
        )
    return CENValidateIdentifierResponse(
        valid=True,
        entity_type=body.entity_type,
        scheme_code=body.scheme_code,
        value_raw=body.value_raw,
        value_canonical=canonical,
        granularity=body.granularity,
    )


@router.post(
    "/identifiers",
    response_model=CENExternalIdentifierResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="RegisterIdentifier",
)
async def register_identifier(
    body: CENRegisterIdentifierRequest,
    db: DbSession,
    tenant: TenantPublisher,
    response: Response,
) -> CENExternalIdentifierResponse:
    _set_standards_header(response)
    await require_access(
        tenant.user,
        "create",
        {"type": "identifier", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = CENAPIService(db)
    try:
        identifier = await service.register_identifier(
            tenant_id=tenant.tenant_id,
            created_by=tenant.user.sub,
            entity_type=IdentifierEntityType(body.entity_type.value),
            scheme_code=body.scheme_code,
            value_raw=body.value_raw,
            granularity=body.granularity,
            dpp_id=body.dpp_id,
            operator_id=body.operator_id,
            facility_id=body.facility_id,
        )
    except CENAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await db.commit()
    await db.refresh(identifier)
    return CENExternalIdentifierResponse(**service.identifiers_to_response(identifier))


@router.post(
    "/identifiers/{identifier_id:uuid}/supersede",
    response_model=CENExternalIdentifierResponse,
    operation_id="SupersedeIdentifier",
)
async def supersede_identifier(
    identifier_id: UUID,
    body: CENSupersedeIdentifierRequest,
    db: DbSession,
    tenant: TenantPublisher,
    response: Response,
) -> CENExternalIdentifierResponse:
    _set_standards_header(response)
    await require_access(
        tenant.user,
        "update",
        {"type": "identifier", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = CENAPIService(db)
    try:
        identifier = await service.supersede_identifier(
            tenant_id=tenant.tenant_id,
            identifier_id=identifier_id,
            replacement_identifier_id=body.replacement_identifier_id,
        )
    except CENAPINotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CENAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await db.commit()
    await db.refresh(identifier)
    return CENExternalIdentifierResponse(**service.identifiers_to_response(identifier))


@router.post(
    "/registrations/dpps/{dpp_id:uuid}",
    response_model=CENSyncResponse,
    operation_id="SyncRegistryForDPP",
)
async def sync_registry_for_dpp(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
    response: Response,
) -> CENSyncResponse:
    _set_standards_header(response)
    await _require_dpp_access(db=db, tenant=tenant, dpp_id=dpp_id, action="publish")
    service = CENAPIService(db)
    try:
        await service.sync_registry_for_dpp(
            tenant_id=tenant.tenant_id,
            dpp_id=dpp_id,
            created_by=tenant.user.sub,
        )
    except CENFeatureDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except CENAPINotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CENAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await db.commit()
    return CENSyncResponse(dpp_id=dpp_id, synced=True, target="registry")


@router.post(
    "/resolutions/dpps/{dpp_id:uuid}",
    response_model=CENSyncResponse,
    operation_id="SyncResolverForDPP",
)
async def sync_resolver_for_dpp(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
    response: Response,
) -> CENSyncResponse:
    _set_standards_header(response)
    await _require_dpp_access(db=db, tenant=tenant, dpp_id=dpp_id, action="publish")
    service = CENAPIService(db)
    try:
        await service.sync_resolver_for_dpp(
            tenant_id=tenant.tenant_id,
            dpp_id=dpp_id,
            created_by=tenant.user.sub,
        )
    except CENFeatureDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except CENAPINotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CENAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await db.commit()
    return CENSyncResponse(dpp_id=dpp_id, synced=True, target="resolver")
