"""Public (unauthenticated) AAS discovery & shell descriptor endpoints.

Follows the ``_resolve_tenant()`` pattern from ``dpps/public_router.py``.
"""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import ShellDescriptorRecord, Tenant, TenantStatus
from app.db.session import DbSession
from app.modules.registry.service import DiscoveryService

router = APIRouter()


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


def _decode_aas_id(aas_id_b64: str) -> str:
    """Decode a base64-URL-safe encoded AAS ID (with padding fix)."""
    try:
        padded = aas_id_b64 + "=" * (-len(aas_id_b64) % 4)
        return base64.urlsafe_b64decode(padded).decode()
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64-encoded AAS identifier",
        ) from exc


class PublicShellDescriptorResponse(BaseModel):
    """Public shell descriptor — excludes internal fields."""

    aas_id: str
    id_short: str
    global_asset_id: str
    specific_asset_ids: list[dict[str, Any]]
    submodel_descriptors: list[dict[str, Any]]


@router.get("/{tenant_slug}/discovery", response_model=list[str])
async def public_discovery_lookup(
    tenant_slug: str,
    db: DbSession,
    key: str = Query(..., description="Asset ID key"),
    value: str = Query(..., description="Asset ID value"),
) -> list[str]:
    """Public discovery: look up AAS IDs by asset ID key/value (no auth)."""
    tenant = await _resolve_tenant(db, tenant_slug)
    svc = DiscoveryService(db)
    return await svc.lookup(tenant.id, key, value)


@router.get(
    "/{tenant_slug}/shell-descriptors/{aas_id_b64}",
    response_model=PublicShellDescriptorResponse,
)
async def public_get_shell_descriptor(
    tenant_slug: str,
    aas_id_b64: str,
    db: DbSession,
) -> PublicShellDescriptorResponse:
    """Public shell descriptor lookup by base64-encoded AAS ID (no auth)."""
    tenant = await _resolve_tenant(db, tenant_slug)
    aas_id = _decode_aas_id(aas_id_b64)

    result = await db.execute(
        select(ShellDescriptorRecord).where(
            ShellDescriptorRecord.tenant_id == tenant.id,
            ShellDescriptorRecord.aas_id == aas_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    return PublicShellDescriptorResponse(
        aas_id=record.aas_id,
        id_short=record.id_short,
        global_asset_id=record.global_asset_id,
        specific_asset_ids=record.specific_asset_ids,
        submodel_descriptors=record.submodel_descriptors,
    )
