"""Public (unauthenticated) endpoints for DID Documents and VC verification."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Tenant, TenantStatus
from app.db.session import DbSession
from app.modules.credentials.did import DIDService
from app.modules.credentials.schemas import VCVerifyRequest, VCVerifyResponse
from app.modules.credentials.vc import VCService

router = APIRouter()

# Singleton: avoid re-parsing PEM on every request
_did_service: DIDService | None = None


def _get_did_service() -> DIDService:
    global _did_service  # noqa: PLW0603
    if _did_service is not None:
        return _did_service
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
    _did_service = DIDService(
        base_url=base_url,
        signing_key_pem=settings.dpp_signing_key,
        key_id=settings.dpp_signing_key_id,
    )
    return _did_service


@router.get(
    "/{tenant_slug}/.well-known/did.json",
    response_model=dict[str, Any],
)
async def get_did_document(tenant_slug: str, db: DbSession) -> dict[str, Any]:
    """Return the DID Document for a tenant (public, no auth).

    Only active tenants get DID documents; unknown slugs return 404.
    """
    # Validate tenant exists and is active
    result = await db.execute(
        select(Tenant.id).where(
            Tenant.slug == tenant_slug.strip().lower(),
            Tenant.status == TenantStatus.ACTIVE,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    did_svc = _get_did_service()
    doc = did_svc.generate_did_document(tenant_slug)
    return doc.model_dump(by_alias=True)


@router.post(
    "/credentials/verify",
    response_model=VCVerifyResponse,
)
async def public_verify_credential(
    body: VCVerifyRequest,
) -> VCVerifyResponse:
    """Publicly verify a Verifiable Credential (no auth required)."""
    did_svc = _get_did_service()
    vc_svc = VCService(did_svc)
    return vc_svc.verify_credential(body.credential)
