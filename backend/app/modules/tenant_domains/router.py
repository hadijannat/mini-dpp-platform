"""Tenant-scoped CRUD APIs for resolver hostnames."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.tenancy import TenantPublisher
from app.db.models import TenantDomain, TenantDomainStatus
from app.db.session import DbSession
from app.modules.tenant_domains.schemas import (
    TenantDomainCreateRequest,
    TenantDomainListResponse,
    TenantDomainResponse,
    TenantDomainUpdateRequest,
)
from app.modules.tenant_domains.service import TenantDomainError, TenantDomainService

router = APIRouter()


def _to_response(row: TenantDomain) -> TenantDomainResponse:
    return TenantDomainResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        hostname=row.hostname,
        status=row.status,
        is_primary=row.is_primary,
        verification_method=row.verification_method,
        verified_at=row.verified_at,
        created_by_subject=row.created_by_subject,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=TenantDomainListResponse)
async def list_tenant_domains(
    db: DbSession,
    tenant: TenantPublisher,
) -> TenantDomainListResponse:
    service = TenantDomainService(db)
    rows = await service.list_domains(tenant.tenant_id)
    return TenantDomainListResponse(items=[_to_response(row) for row in rows], count=len(rows))


@router.post("", response_model=TenantDomainResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_domain(
    body: TenantDomainCreateRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> TenantDomainResponse:
    service = TenantDomainService(db)
    try:
        row = await service.create_domain(
            tenant_id=tenant.tenant_id,
            created_by=tenant.user.sub,
            hostname=body.hostname,
            is_primary=body.is_primary,
        )
    except TenantDomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await db.commit()
    await db.refresh(row)
    return _to_response(row)


@router.patch("/{domain_id:uuid}", response_model=TenantDomainResponse)
async def update_tenant_domain(
    domain_id: UUID,
    body: TenantDomainUpdateRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> TenantDomainResponse:
    if body.status == TenantDomainStatus.ACTIVE and not tenant.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin role required to activate domains",
        )
    if body.verification_method is not None and not tenant.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin role required to set verification method",
        )

    service = TenantDomainService(db)
    try:
        row = await service.update_domain(
            domain_id=domain_id,
            tenant_id=tenant.tenant_id,
            hostname=body.hostname,
            status=body.status,
            is_primary=body.is_primary,
            verification_method=body.verification_method,
        )
    except TenantDomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    await db.commit()
    await db.refresh(row)
    return _to_response(row)


@router.delete("/{domain_id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_domain(
    domain_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> None:
    service = TenantDomainService(db)
    try:
        deleted = await service.delete_domain(domain_id=domain_id, tenant_id=tenant.tenant_id)
    except TenantDomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    await db.commit()
