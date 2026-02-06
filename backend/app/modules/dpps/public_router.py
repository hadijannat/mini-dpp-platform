"""
Public (unauthenticated) API for reading published Digital Product Passports.

EU ESPR requires published DPPs to be accessible without authentication.
Only DPPs with status=PUBLISHED are served; drafts/archived return 404.
"""

from __future__ import annotations

import copy
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import DPP, DPPRevision, DPPStatus, Tenant, TenantStatus
from app.db.session import DbSession


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
