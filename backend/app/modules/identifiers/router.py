"""Tenant-scoped identifier governance routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.core.security import require_access
from app.core.tenancy import TenantPublisher
from app.db.models import DataCarrierIdentityLevel as DBGranularity
from app.db.models import EconomicOperator, ExternalIdentifier, Facility, IdentifierEntityType
from app.db.session import DbSession
from app.modules.identifiers.schemas import (
    EconomicOperatorCreateRequest,
    EconomicOperatorResponse,
    ExternalIdentifierResponse,
    FacilityCreateRequest,
    FacilityResponse,
    IdentifierGranularity,
    IdentifierRegisterRequest,
    IdentifierSupersedeRequest,
    IdentifierValidateRequest,
    IdentifierValidateResponse,
)
from app.modules.identifiers.schemas import (
    IdentifierEntityType as SchemaEntityType,
)
from app.modules.identifiers.service import IdentifierModuleService
from app.standards.cen_pren.identifiers_18219 import IdentifierGovernanceError

router = APIRouter()


def _to_db_entity_type(entity_type: SchemaEntityType) -> IdentifierEntityType:
    return IdentifierEntityType(entity_type.value)


def _to_db_granularity(granularity: IdentifierGranularity | None) -> DBGranularity | None:
    if granularity is None:
        return None
    return DBGranularity(granularity.value)


def _to_identifier_response(identifier: ExternalIdentifier) -> ExternalIdentifierResponse:
    return ExternalIdentifierResponse(
        id=identifier.id,
        tenant_id=identifier.tenant_id,
        entity_type=identifier.entity_type.value,
        scheme_code=identifier.scheme_code,
        value_raw=identifier.value_raw,
        value_canonical=identifier.value_canonical,
        granularity=identifier.granularity.value if identifier.granularity else None,
        status=identifier.status.value,
        replaced_by_identifier_id=identifier.replaced_by_identifier_id,
        issued_at=identifier.issued_at,
        deprecates_at=identifier.deprecates_at,
        created_by_subject=identifier.created_by_subject,
        created_at=identifier.created_at,
        updated_at=identifier.updated_at,
    )


def _to_operator_response(operator: EconomicOperator) -> EconomicOperatorResponse:
    return EconomicOperatorResponse(
        id=operator.id,
        tenant_id=operator.tenant_id,
        legal_name=operator.legal_name,
        country=operator.country,
        metadata_json=operator.metadata_json,
        created_by_subject=operator.created_by_subject,
        created_at=operator.created_at,
        updated_at=operator.updated_at,
    )


def _to_facility_response(facility: Facility) -> FacilityResponse:
    return FacilityResponse(
        id=facility.id,
        tenant_id=facility.tenant_id,
        operator_id=facility.operator_id,
        facility_name=facility.facility_name,
        address=facility.address,
        metadata_json=facility.metadata_json,
        created_by_subject=facility.created_by_subject,
        created_at=facility.created_at,
        updated_at=facility.updated_at,
    )


@router.post("/validate", response_model=IdentifierValidateResponse)
async def validate_identifier(
    body: IdentifierValidateRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> IdentifierValidateResponse:
    await require_access(
        tenant.user,
        "create",
        {"type": "identifier", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = IdentifierModuleService(db)
    try:
        canonical = await service.validate_identifier(
            scheme_code=body.scheme_code,
            value_raw=body.value_raw,
            entity_type=_to_db_entity_type(body.entity_type),
            granularity=_to_db_granularity(body.granularity),
        )
    except IdentifierGovernanceError as exc:
        return IdentifierValidateResponse(
            valid=False,
            entity_type=body.entity_type,
            scheme_code=body.scheme_code,
            value_raw=body.value_raw,
            granularity=body.granularity,
            errors=[str(exc)],
        )
    return IdentifierValidateResponse(
        valid=True,
        entity_type=body.entity_type,
        scheme_code=body.scheme_code,
        value_raw=body.value_raw,
        value_canonical=canonical,
        granularity=body.granularity,
    )


@router.post("", response_model=ExternalIdentifierResponse, status_code=status.HTTP_201_CREATED)
async def register_identifier(
    body: IdentifierRegisterRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> ExternalIdentifierResponse:
    await require_access(
        tenant.user,
        "create",
        {"type": "identifier", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = IdentifierModuleService(db)
    try:
        identifier = await service.register_identifier(
            tenant_id=tenant.tenant_id,
            created_by=tenant.user.sub,
            entity_type=_to_db_entity_type(body.entity_type),
            scheme_code=body.scheme_code,
            value_raw=body.value_raw,
            granularity=_to_db_granularity(body.granularity),
            dpp_id=body.dpp_id,
            operator_id=body.operator_id,
            facility_id=body.facility_id,
        )
    except IdentifierGovernanceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(identifier)
    return _to_identifier_response(identifier)


@router.get("", response_model=list[ExternalIdentifierResponse])
async def list_identifiers(
    db: DbSession,
    tenant: TenantPublisher,
    entity_type: SchemaEntityType | None = Query(default=None),
    scheme_code: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ExternalIdentifierResponse]:
    await require_access(
        tenant.user,
        "read",
        {"type": "identifier", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = IdentifierModuleService(db)
    identifiers = await service.list_identifiers(
        tenant_id=tenant.tenant_id,
        entity_type=_to_db_entity_type(entity_type) if entity_type else None,
        scheme_code=scheme_code,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [_to_identifier_response(item) for item in identifiers]


@router.get("/{identifier_id:uuid}", response_model=ExternalIdentifierResponse)
async def get_identifier(
    identifier_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> ExternalIdentifierResponse:
    await require_access(
        tenant.user,
        "read",
        {"type": "identifier", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = IdentifierModuleService(db)
    identifier = await service.get_identifier(tenant_id=tenant.tenant_id, identifier_id=identifier_id)
    if identifier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identifier not found")
    return _to_identifier_response(identifier)


@router.post("/{identifier_id:uuid}/supersede", response_model=ExternalIdentifierResponse)
async def supersede_identifier(
    identifier_id: UUID,
    body: IdentifierSupersedeRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> ExternalIdentifierResponse:
    await require_access(
        tenant.user,
        "update",
        {"type": "identifier", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = IdentifierModuleService(db)
    try:
        identifier = await service.supersede_identifier(
            tenant_id=tenant.tenant_id,
            identifier_id=identifier_id,
            replacement_identifier_id=body.replacement_identifier_id,
        )
    except IdentifierGovernanceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(identifier)
    return _to_identifier_response(identifier)


@router.post("/operators", response_model=EconomicOperatorResponse, status_code=status.HTTP_201_CREATED)
async def create_operator(
    body: EconomicOperatorCreateRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> EconomicOperatorResponse:
    await require_access(
        tenant.user,
        "create",
        {"type": "economic_operator", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = IdentifierModuleService(db)
    operator = await service.create_operator(
        tenant_id=tenant.tenant_id,
        created_by=tenant.user.sub,
        legal_name=body.legal_name,
        country=body.country,
        metadata_json=body.metadata_json,
    )
    if body.identifier is not None:
        try:
            await service.register_identifier(
                tenant_id=tenant.tenant_id,
                created_by=tenant.user.sub,
                entity_type=IdentifierEntityType.OPERATOR,
                scheme_code=body.identifier.scheme_code,
                value_raw=body.identifier.value_raw,
                granularity=_to_db_granularity(body.identifier.granularity),
                operator_id=operator.id,
            )
        except IdentifierGovernanceError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
    await db.commit()
    await db.refresh(operator)
    return _to_operator_response(operator)


@router.get("/operators", response_model=list[EconomicOperatorResponse])
async def list_operators(
    db: DbSession,
    tenant: TenantPublisher,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[EconomicOperatorResponse]:
    await require_access(
        tenant.user,
        "read",
        {"type": "economic_operator", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = IdentifierModuleService(db)
    operators = await service.list_operators(tenant_id=tenant.tenant_id, limit=limit, offset=offset)
    return [_to_operator_response(item) for item in operators]


@router.post("/facilities", response_model=FacilityResponse, status_code=status.HTTP_201_CREATED)
async def create_facility(
    body: FacilityCreateRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> FacilityResponse:
    await require_access(
        tenant.user,
        "create",
        {"type": "facility", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = IdentifierModuleService(db)
    try:
        facility = await service.create_facility(
            tenant_id=tenant.tenant_id,
            created_by=tenant.user.sub,
            operator_id=body.operator_id,
            facility_name=body.facility_name,
            address=body.address,
            metadata_json=body.metadata_json,
        )
        if body.identifier is not None:
            await service.register_identifier(
                tenant_id=tenant.tenant_id,
                created_by=tenant.user.sub,
                entity_type=IdentifierEntityType.FACILITY,
                scheme_code=body.identifier.scheme_code,
                value_raw=body.identifier.value_raw,
                granularity=_to_db_granularity(body.identifier.granularity),
                facility_id=facility.id,
            )
    except IdentifierGovernanceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(facility)
    return _to_facility_response(facility)


@router.get("/facilities", response_model=list[FacilityResponse])
async def list_facilities(
    db: DbSession,
    tenant: TenantPublisher,
    operator_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[FacilityResponse]:
    await require_access(
        tenant.user,
        "read",
        {"type": "facility", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = IdentifierModuleService(db)
    facilities = await service.list_facilities(
        tenant_id=tenant.tenant_id,
        operator_id=operator_id,
        limit=limit,
        offset=offset,
    )
    return [_to_facility_response(item) for item in facilities]
