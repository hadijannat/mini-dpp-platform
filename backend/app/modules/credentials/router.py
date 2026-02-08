"""Tenant-scoped authenticated routes for Verifiable Credentials."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import get_settings
from app.core.tenancy import TenantPublisher
from app.db.models import DPPStatus
from app.db.session import DbSession
from app.modules.credentials.did import DIDService
from app.modules.credentials.schemas import (
    IssuedCredentialResponse,
    VCIssueRequest,
    VCVerifyRequest,
    VCVerifyResponse,
)
from app.modules.credentials.vc import VCService

router = APIRouter()

# Singleton: avoid re-parsing PEM key on every request
_vc_service: VCService | None = None


def _get_vc_service() -> VCService:
    """Build VCService from application settings (cached singleton)."""
    global _vc_service  # noqa: PLW0603
    if _vc_service is not None:
        return _vc_service
    settings = get_settings()
    if not settings.vc_enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Verifiable Credentials are not enabled",
        )
    if not settings.dpp_signing_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Signing key is not configured",
        )
    base_url = settings.resolver_base_url or "https://localhost"
    did_svc = DIDService(
        base_url=base_url,
        signing_key_pem=settings.dpp_signing_key,
        key_id=settings.dpp_signing_key_id,
    )
    _vc_service = VCService(did_svc)
    return _vc_service


def _record_to_response(rec: object) -> IssuedCredentialResponse:
    from app.db.models import IssuedCredential

    assert isinstance(rec, IssuedCredential)
    return IssuedCredentialResponse(
        id=rec.id,
        dpp_id=rec.dpp_id,
        issuer_did=rec.issuer_did,
        subject_id=rec.subject_id,
        issuance_date=rec.issuance_date,
        expiration_date=rec.expiration_date,
        revoked=rec.revoked,
        credential=rec.credential_json,
        created_at=rec.created_at,
    )


@router.post(
    "/issue/{dpp_id}",
    response_model=IssuedCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def issue_credential(
    dpp_id: UUID,
    body: VCIssueRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> IssuedCredentialResponse:
    """Issue a Verifiable Credential for a published DPP."""
    svc = _get_vc_service()

    # Fetch DPP
    from sqlalchemy import select

    from app.db.models import DPP

    stmt = select(DPP).where(DPP.id == dpp_id, DPP.tenant_id == tenant.tenant_id)
    result = await db.execute(stmt)
    dpp = result.scalar_one_or_none()
    if not dpp:
        raise HTTPException(status_code=404, detail="DPP not found")
    if dpp.status != DPPStatus.PUBLISHED:
        raise HTTPException(
            status_code=400,
            detail="Only published DPPs can have credentials issued",
        )

    # Fetch published revision
    if not dpp.current_published_revision_id:
        raise HTTPException(status_code=400, detail="No published revision")

    from app.db.models import DPPRevision

    rev_stmt = select(DPPRevision).where(DPPRevision.id == dpp.current_published_revision_id)
    rev_result = await db.execute(rev_stmt)
    revision = rev_result.scalar_one_or_none()
    if not revision:
        raise HTTPException(status_code=400, detail="Published revision not found")

    record = await svc.issue_credential(
        dpp=dpp,
        revision=revision,
        tenant_slug=tenant.tenant_slug,
        expiration_days=body.expiration_days,
        created_by=tenant.user.sub,
        db=db,
    )
    await db.commit()
    return _record_to_response(record)


@router.post("/verify", response_model=VCVerifyResponse)
async def verify_credential(
    body: VCVerifyRequest,
    _tenant: TenantPublisher,
) -> VCVerifyResponse:
    """Verify a Verifiable Credential."""
    svc = _get_vc_service()
    return svc.verify_credential(body.credential)


@router.get("/{dpp_id}", response_model=IssuedCredentialResponse)
async def get_credential(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> IssuedCredentialResponse:
    """Get the issued credential for a DPP."""
    svc = _get_vc_service()
    record = await svc.get_credential_for_dpp(dpp_id, tenant.tenant_id, db)
    if not record:
        raise HTTPException(status_code=404, detail="No credential found for this DPP")
    return _record_to_response(record)


@router.get("", response_model=list[IssuedCredentialResponse])
async def list_credentials(
    db: DbSession,
    tenant: TenantPublisher,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[IssuedCredentialResponse]:
    """List issued credentials for the tenant."""
    svc = _get_vc_service()
    records = await svc.list_credentials(tenant.tenant_id, db, limit=limit, offset=offset)
    return [_record_to_response(r) for r in records]
