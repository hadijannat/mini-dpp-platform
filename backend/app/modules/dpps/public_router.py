"""
Public (unauthenticated) API for reading published Digital Product Passports.

EU ESPR requires published DPPs to be accessible without authentication.
Only DPPs with status=PUBLISHED are served; drafts/archived return 404.
"""

from __future__ import annotations

import base64
import copy
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import DPP, DPPRevision, DPPStatus, Tenant, TenantStatus
from app.db.session import DbSession
from app.modules.dpps.repository import AASRepositoryService
from app.modules.dpps.submodel_filter import filter_aas_env_by_espr_tier


def _filter_public_aas_environment(aas_env: dict[str, Any]) -> dict[str, Any]:
    """Remove non-public elements from AAS environment for unauthenticated access."""
    filtered = copy.deepcopy(aas_env)
    for submodel in filtered.get("submodels", []):
        elements = submodel.get("submodelElements", [])
        submodel["submodelElements"] = [el for el in elements if _element_is_public(el)]
    return filtered


def _element_is_public(element: dict[str, Any]) -> bool:
    """Check if an element's confidentiality qualifiers allow public access."""
    qualifiers = element.get("qualifiers", [])
    for q in qualifiers:
        if q.get("type") == "Confidentiality":
            return str(q.get("value", "public")).lower() == "public"
    return True


router = APIRouter()


class PublicDPPResponse(BaseModel):
    """Public response for a published DPP — no sensitive fields."""

    id: UUID
    status: str
    asset_ids: dict[str, Any]
    created_at: str
    updated_at: str
    current_revision_no: int | None
    aas_environment: dict[str, Any] | None
    digest_sha256: str | None


async def _resolve_tenant(db: DbSession, tenant_slug: str) -> Tenant:
    """Look up an active tenant by slug (no auth required)."""
    result = await db.execute(
        select(Tenant).where(
            Tenant.slug == tenant_slug.strip().lower(),
            Tenant.status == TenantStatus.ACTIVE,
        )
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
    return tenant


@router.get(
    "/{tenant_slug}/dpps/{dpp_id}",
    response_model=PublicDPPResponse,
)
async def get_published_dpp(
    tenant_slug: str,
    dpp_id: UUID,
    db: DbSession,
) -> PublicDPPResponse:
    """
    Get a published DPP by ID (no authentication required).

    Only returns DPPs with status=PUBLISHED. Drafts and archived DPPs return 404.
    """
    tenant = await _resolve_tenant(db, tenant_slug)

    result = await db.execute(
        select(DPP).where(
            DPP.id == dpp_id,
            DPP.tenant_id == tenant.id,
            DPP.status == DPPStatus.PUBLISHED,
        )
    )
    dpp = result.scalar_one_or_none()
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    revision = await _get_published_revision(db, dpp)

    return PublicDPPResponse(
        id=dpp.id,
        status=dpp.status.value,
        asset_ids=dpp.asset_ids,
        created_at=dpp.created_at.isoformat(),
        updated_at=dpp.updated_at.isoformat(),
        current_revision_no=revision.revision_no if revision else None,
        aas_environment=_filter_public_aas_environment(revision.aas_env_json) if revision else None,
        digest_sha256=revision.digest_sha256 if revision else None,
    )


@router.get(
    "/{tenant_slug}/dpps/slug/{slug}",
    response_model=PublicDPPResponse,
)
async def get_published_dpp_by_slug(
    tenant_slug: str,
    slug: str,
    db: DbSession,
) -> PublicDPPResponse:
    """
    Get a published DPP by its short-link slug (no authentication required).

    The slug is the first 8 hex characters of the DPP UUID,
    as used in QR code short links.
    """
    tenant = await _resolve_tenant(db, tenant_slug)

    if not slug or len(slug) != 8:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        int(slug.lower(), 16)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    from sqlalchemy import String, cast

    result = await db.execute(
        select(DPP)
        .where(
            cast(DPP.id, String).like(f"{slug.lower()[:8]}%"),
            DPP.tenant_id == tenant.id,
            DPP.status == DPPStatus.PUBLISHED,
        )
        .limit(2)
    )
    matches = list(result.scalars().all())
    if len(matches) != 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    dpp = matches[0]
    revision = await _get_published_revision(db, dpp)

    return PublicDPPResponse(
        id=dpp.id,
        status=dpp.status.value,
        asset_ids=dpp.asset_ids,
        created_at=dpp.created_at.isoformat(),
        updated_at=dpp.updated_at.isoformat(),
        current_revision_no=revision.revision_no if revision else None,
        aas_environment=_filter_public_aas_environment(revision.aas_env_json) if revision else None,
        digest_sha256=revision.digest_sha256 if revision else None,
    )


async def _get_published_revision(
    db: DbSession,
    dpp: DPP,
) -> DPPRevision | None:
    """Get the current published revision for a DPP."""
    if not dpp.current_published_revision_id:
        return None
    result = await db.execute(
        select(DPPRevision).where(
            DPPRevision.id == dpp.current_published_revision_id,
            DPPRevision.tenant_id == dpp.tenant_id,
        )
    )
    return result.scalar_one_or_none()


# =============================================================================
# IDTA-01002 AAS Repository Endpoints
# =============================================================================


def _decode_b64(encoded: str) -> str:
    """Decode a base64url-encoded identifier, adding padding as needed."""
    padded = encoded + "=" * (4 - len(encoded) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64url-encoded identifier",
        )


@router.get(
    "/{tenant_slug}/shells/{aas_id_b64}",
    response_model=PublicDPPResponse,
)
async def get_shell_by_aas_id(
    tenant_slug: str,
    aas_id_b64: str,
    db: DbSession,
    espr_tier: str | None = Query(default=None, alias="espr_tier"),
) -> PublicDPPResponse:
    """IDTA-01002 AAS Repository -- Get a shell (DPP) by base64url-encoded AAS ID."""
    tenant = await _resolve_tenant(db, tenant_slug)
    aas_id = _decode_b64(aas_id_b64)

    repo = AASRepositoryService(db)
    dpp = await repo.get_shell_by_aas_id(tenant.id, aas_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    revision = await repo.get_published_revision(dpp)
    aas_env: dict[str, Any] | None = None
    if revision:
        aas_env = _filter_public_aas_environment(revision.aas_env_json)
        aas_env = filter_aas_env_by_espr_tier(aas_env, espr_tier, in_place=True)

    return PublicDPPResponse(
        id=dpp.id,
        status=dpp.status.value,
        asset_ids=dpp.asset_ids,
        created_at=dpp.created_at.isoformat(),
        updated_at=dpp.updated_at.isoformat(),
        current_revision_no=revision.revision_no if revision else None,
        aas_environment=aas_env,
        digest_sha256=revision.digest_sha256 if revision else None,
    )


@router.get(
    "/{tenant_slug}/shells/{aas_id_b64}/submodels/{submodel_id_b64}",
)
async def get_submodel_by_id(
    tenant_slug: str,
    aas_id_b64: str,
    submodel_id_b64: str,
    db: DbSession,
    espr_tier: str | None = Query(default=None, alias="espr_tier"),
) -> dict[str, Any]:
    """Get a specific submodel from a published DPP."""
    tenant = await _resolve_tenant(db, tenant_slug)
    aas_id = _decode_b64(aas_id_b64)
    submodel_id = _decode_b64(submodel_id_b64)

    repo = AASRepositoryService(db)
    dpp = await repo.get_shell_by_aas_id(tenant.id, aas_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    revision = await repo.get_published_revision(dpp)
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    # Apply confidentiality + tier filters, then extract
    aas_env = _filter_public_aas_environment(revision.aas_env_json)
    aas_env = filter_aas_env_by_espr_tier(aas_env, espr_tier)

    submodel = repo.get_submodel_from_revision(aas_env, submodel_id)
    if not submodel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submodel not found",
        )

    return submodel


@router.get(
    "/{tenant_slug}/shells/{aas_id_b64}/submodels/{submodel_id_b64}/$value",
)
async def get_submodel_value(
    tenant_slug: str,
    aas_id_b64: str,
    submodel_id_b64: str,
    db: DbSession,
    espr_tier: str | None = Query(default=None, alias="espr_tier"),
) -> dict[str, Any]:
    """Get submodel $value (submodelElements only) -- Catena-X standard endpoint."""
    tenant = await _resolve_tenant(db, tenant_slug)
    aas_id = _decode_b64(aas_id_b64)
    submodel_id = _decode_b64(submodel_id_b64)

    repo = AASRepositoryService(db)
    dpp = await repo.get_shell_by_aas_id(tenant.id, aas_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    revision = await repo.get_published_revision(dpp)
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    aas_env = _filter_public_aas_environment(revision.aas_env_json)
    aas_env = filter_aas_env_by_espr_tier(aas_env, espr_tier)

    submodel = repo.get_submodel_from_revision(aas_env, submodel_id)
    if not submodel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submodel not found",
        )

    return {"submodelElements": submodel.get("submodelElements", [])}
