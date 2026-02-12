"""Tenant-scoped APIs for lifecycle-managed data carriers."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.security import require_access
from app.core.security.resource_context import build_dpp_resource_context
from app.core.tenancy import TenantPublisher
from app.db.models import DataCarrier
from app.db.session import DbSession
from app.modules.data_carriers.schemas import (
    DataCarrierCreateRequest,
    DataCarrierDeprecateRequest,
    DataCarrierIdentifierScheme,
    DataCarrierIdentityLevel,
    DataCarrierListResponse,
    DataCarrierPreSalePackResponse,
    DataCarrierRegistryExportResponse,
    DataCarrierReissueRequest,
    DataCarrierRenderRequest,
    DataCarrierResponse,
    DataCarrierStatus,
    DataCarrierUpdateRequest,
    DataCarrierWithdrawRequest,
    RegistryExportFormat,
)
from app.modules.data_carriers.service import DataCarrierError, DataCarrierService
from app.modules.dpps.service import DPPService

router = APIRouter()


def _carrier_to_response(carrier: DataCarrier) -> DataCarrierResponse:
    return DataCarrierResponse(
        id=carrier.id,
        tenant_id=carrier.tenant_id,
        dpp_id=carrier.dpp_id,
        identity_level=carrier.identity_level.value,
        identifier_scheme=carrier.identifier_scheme.value,
        carrier_type=carrier.carrier_type.value,
        resolver_strategy=carrier.resolver_strategy.value,
        status=carrier.status.value,
        identifier_key=carrier.identifier_key,
        identifier_data={str(k): str(v) for k, v in (carrier.identifier_data or {}).items()},
        encoded_uri=carrier.encoded_uri,
        layout_profile=carrier.layout_profile or {},
        placement_metadata=carrier.placement_metadata or {},
        pre_sale_enabled=carrier.pre_sale_enabled,
        is_gtin_verified=carrier.is_gtin_verified,
        replaced_by_carrier_id=carrier.replaced_by_carrier_id,
        withdrawn_reason=carrier.withdrawn_reason,
        created_by_subject=carrier.created_by_subject,
        created_at=carrier.created_at,
        updated_at=carrier.updated_at,
    )


async def _require_dpp_read_access(db: DbSession, tenant: TenantPublisher, dpp_id: UUID) -> None:
    dpp_service = DPPService(db)
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
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
        "read",
        build_dpp_resource_context(dpp, shared_with_current_user=shared_with_current_user),
        tenant=tenant,
    )


async def _require_dpp_update_access(db: DbSession, tenant: TenantPublisher, dpp_id: UUID) -> None:
    dpp_service = DPPService(db)
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
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
        "update",
        build_dpp_resource_context(dpp, shared_with_current_user=shared_with_current_user),
        tenant=tenant,
    )


@router.post("", response_model=DataCarrierResponse, status_code=status.HTTP_201_CREATED)
async def create_data_carrier(
    body: DataCarrierCreateRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> DataCarrierResponse:
    await _require_dpp_update_access(db, tenant, body.dpp_id)
    service = DataCarrierService(db)
    try:
        carrier = await service.create_carrier(
            tenant_id=tenant.tenant_id,
            tenant_slug=tenant.tenant_slug,
            created_by=tenant.user.sub,
            request=body,
        )
    except DataCarrierError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(carrier)
    return _carrier_to_response(carrier)


@router.get("", response_model=DataCarrierListResponse)
async def list_data_carriers(
    db: DbSession,
    tenant: TenantPublisher,
    dpp_id: UUID | None = Query(default=None),
    status_filter: DataCarrierStatus | None = Query(default=None, alias="status"),
    identity_level: DataCarrierIdentityLevel | None = Query(default=None),
    identifier_scheme: DataCarrierIdentifierScheme | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DataCarrierListResponse:
    if dpp_id is not None:
        await _require_dpp_read_access(db, tenant, dpp_id)

    service = DataCarrierService(db)
    items = await service.list_carriers(
        tenant_id=tenant.tenant_id,
        dpp_id=dpp_id,
        status=status_filter,
        identity_level=identity_level,
        identifier_scheme=identifier_scheme,
        limit=limit,
        offset=offset,
    )
    return DataCarrierListResponse(items=[_carrier_to_response(item) for item in items], count=len(items))


@router.get("/{carrier_id:uuid}", response_model=DataCarrierResponse)
async def get_data_carrier(
    carrier_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> DataCarrierResponse:
    service = DataCarrierService(db)
    carrier = await service.get_carrier(carrier_id, tenant.tenant_id)
    if carrier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carrier not found")
    await _require_dpp_read_access(db, tenant, carrier.dpp_id)
    return _carrier_to_response(carrier)


@router.patch("/{carrier_id:uuid}", response_model=DataCarrierResponse)
async def update_data_carrier(
    carrier_id: UUID,
    body: DataCarrierUpdateRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> DataCarrierResponse:
    service = DataCarrierService(db)
    existing = await service.get_carrier(carrier_id, tenant.tenant_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carrier not found")
    await _require_dpp_update_access(db, tenant, existing.dpp_id)
    try:
        carrier = await service.update_carrier(
            carrier_id=carrier_id,
            tenant_id=tenant.tenant_id,
            tenant_slug=tenant.tenant_slug,
            request=body,
            updated_by=tenant.user.sub,
        )
    except DataCarrierError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(carrier)
    return _carrier_to_response(carrier)


@router.post("/{carrier_id:uuid}/render")
async def render_data_carrier(
    carrier_id: UUID,
    body: DataCarrierRenderRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> Response:
    service = DataCarrierService(db)
    carrier = await service.get_carrier(carrier_id, tenant.tenant_id)
    if carrier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carrier not found")
    await _require_dpp_read_access(db, tenant, carrier.dpp_id)
    try:
        rendered = await service.render_carrier(
            carrier_id=carrier_id,
            tenant_id=tenant.tenant_id,
            request=body,
        )
    except DataCarrierError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    await db.commit()
    return Response(
        content=rendered.payload,
        media_type=rendered.media_type,
        headers={
            "Content-Disposition": (
                f'inline; filename="data-carrier-{carrier.id}.{rendered.extension}"'
            )
        },
    )


@router.post("/{carrier_id:uuid}/lifecycle/deprecate", response_model=DataCarrierResponse)
async def deprecate_data_carrier(
    carrier_id: UUID,
    body: DataCarrierDeprecateRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> DataCarrierResponse:
    service = DataCarrierService(db)
    existing = await service.get_carrier(carrier_id, tenant.tenant_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carrier not found")
    await _require_dpp_update_access(db, tenant, existing.dpp_id)
    try:
        carrier = await service.deprecate_carrier(
            carrier_id=carrier_id,
            tenant_id=tenant.tenant_id,
            tenant_slug=tenant.tenant_slug,
            request=body,
            updated_by=tenant.user.sub,
        )
    except DataCarrierError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(carrier)
    return _carrier_to_response(carrier)


@router.post("/{carrier_id:uuid}/lifecycle/withdraw", response_model=DataCarrierResponse)
async def withdraw_data_carrier(
    carrier_id: UUID,
    body: DataCarrierWithdrawRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> DataCarrierResponse:
    service = DataCarrierService(db)
    existing = await service.get_carrier(carrier_id, tenant.tenant_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carrier not found")
    await _require_dpp_update_access(db, tenant, existing.dpp_id)
    try:
        carrier = await service.withdraw_carrier(
            carrier_id=carrier_id,
            tenant_id=tenant.tenant_id,
            tenant_slug=tenant.tenant_slug,
            request=body,
            updated_by=tenant.user.sub,
        )
    except DataCarrierError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(carrier)
    return _carrier_to_response(carrier)


@router.post("/{carrier_id:uuid}/lifecycle/reissue", response_model=DataCarrierResponse)
async def reissue_data_carrier(
    carrier_id: UUID,
    body: DataCarrierReissueRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> DataCarrierResponse:
    service = DataCarrierService(db)
    existing = await service.get_carrier(carrier_id, tenant.tenant_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carrier not found")
    await _require_dpp_update_access(db, tenant, existing.dpp_id)
    try:
        carrier = await service.reissue_carrier(
            carrier_id=carrier_id,
            tenant_id=tenant.tenant_id,
            tenant_slug=tenant.tenant_slug,
            request=body,
            updated_by=tenant.user.sub,
        )
    except DataCarrierError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(carrier)
    return _carrier_to_response(carrier)


@router.get("/{carrier_id:uuid}/pre-sale-pack", response_model=DataCarrierPreSalePackResponse)
async def get_pre_sale_pack(
    carrier_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> DataCarrierPreSalePackResponse:
    service = DataCarrierService(db)
    carrier = await service.get_carrier(carrier_id, tenant.tenant_id)
    if carrier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carrier not found")
    await _require_dpp_read_access(db, tenant, carrier.dpp_id)
    try:
        return await service.build_pre_sale_pack(
            carrier_id=carrier_id,
            tenant_id=tenant.tenant_id,
            tenant_slug=tenant.tenant_slug,
        )
    except DataCarrierError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/registry-export", response_model=DataCarrierRegistryExportResponse)
async def export_registry(
    db: DbSession,
    tenant: TenantPublisher,
    format: RegistryExportFormat = Query(default=RegistryExportFormat.JSON),
) -> DataCarrierRegistryExportResponse | Response:
    service = DataCarrierService(db)
    payload = await service.export_registry_payload(tenant_id=tenant.tenant_id)
    if format == RegistryExportFormat.CSV:
        csv_content = service.registry_payload_to_csv(payload)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=data-carriers-registry-export.csv"
            },
        )
    return payload
