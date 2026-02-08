"""Tenant-scoped AAS Registry CRUD routes."""

from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException, Query, status

from app.core.tenancy import TenantPublisher
from app.db.session import DbSession
from app.modules.registry.schemas import (
    AssetDiscoveryCreate,
    AssetDiscoveryResponse,
    RegistrySearchRequest,
    ShellDescriptorCreate,
    ShellDescriptorResponse,
    ShellDescriptorUpdate,
    SubmodelDescriptorResponse,
)
from app.modules.registry.service import BuiltInRegistryService, DiscoveryService

router = APIRouter()


def _decode_aas_id(aas_id_b64: str) -> str:
    """Decode a base64-URL-safe encoded AAS ID (with padding fix)."""
    padded = aas_id_b64 + "=" * (-len(aas_id_b64) % 4)
    return base64.urlsafe_b64decode(padded).decode()


def _descriptor_to_response(record: object) -> ShellDescriptorResponse:
    """Convert a ShellDescriptorRecord to response schema."""
    from app.db.models import ShellDescriptorRecord

    assert isinstance(record, ShellDescriptorRecord)
    return ShellDescriptorResponse(
        id=record.id,
        tenant_id=record.tenant_id,
        aas_id=record.aas_id,
        id_short=record.id_short,
        global_asset_id=record.global_asset_id,
        specific_asset_ids=record.specific_asset_ids,
        submodel_descriptors=record.submodel_descriptors,
        dpp_id=record.dpp_id,
        created_by_subject=record.created_by_subject,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


# ---- Shell Descriptor CRUD ----


@router.get("/shell-descriptors", response_model=list[ShellDescriptorResponse])
async def list_shell_descriptors(
    db: DbSession,
    tenant: TenantPublisher,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ShellDescriptorResponse]:
    """List all shell descriptors for the current tenant."""
    svc = BuiltInRegistryService(db)
    records = await svc.list_shell_descriptors(tenant.tenant_id, limit, offset)
    return [_descriptor_to_response(r) for r in records]


@router.post(
    "/shell-descriptors",
    response_model=ShellDescriptorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_shell_descriptor(
    body: ShellDescriptorCreate,
    db: DbSession,
    tenant: TenantPublisher,
) -> ShellDescriptorResponse:
    """Create a new shell descriptor."""
    svc = BuiltInRegistryService(db)
    record = await svc.create_shell_descriptor(
        tenant_id=tenant.tenant_id,
        descriptor_create=body,
        created_by=tenant.user.sub,
    )
    return _descriptor_to_response(record)


@router.get(
    "/shell-descriptors/{aas_id_b64}",
    response_model=ShellDescriptorResponse,
)
async def get_shell_descriptor(
    aas_id_b64: str,
    db: DbSession,
    tenant: TenantPublisher,
) -> ShellDescriptorResponse:
    """Get a shell descriptor by base64-encoded AAS ID."""
    aas_id = _decode_aas_id(aas_id_b64)
    svc = BuiltInRegistryService(db)
    record = await svc.get_shell_descriptor(tenant.tenant_id, aas_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shell descriptor not found",
        )
    return _descriptor_to_response(record)


@router.put(
    "/shell-descriptors/{aas_id_b64}",
    response_model=ShellDescriptorResponse,
)
async def update_shell_descriptor(
    aas_id_b64: str,
    body: ShellDescriptorUpdate,
    db: DbSession,
    tenant: TenantPublisher,
) -> ShellDescriptorResponse:
    """Update a shell descriptor by base64-encoded AAS ID."""
    aas_id = _decode_aas_id(aas_id_b64)
    svc = BuiltInRegistryService(db)
    record = await svc.update_shell_descriptor(tenant.tenant_id, aas_id, body)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shell descriptor not found",
        )
    return _descriptor_to_response(record)


@router.delete(
    "/shell-descriptors/{aas_id_b64}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_shell_descriptor(
    aas_id_b64: str,
    db: DbSession,
    tenant: TenantPublisher,
) -> None:
    """Delete a shell descriptor by base64-encoded AAS ID."""
    aas_id = _decode_aas_id(aas_id_b64)
    svc = BuiltInRegistryService(db)
    deleted = await svc.delete_shell_descriptor(tenant.tenant_id, aas_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shell descriptor not found",
        )


@router.get(
    "/shell-descriptors/{aas_id_b64}/submodel-descriptors",
    response_model=list[SubmodelDescriptorResponse],
)
async def list_submodel_descriptors(
    aas_id_b64: str,
    db: DbSession,
    tenant: TenantPublisher,
) -> list[SubmodelDescriptorResponse]:
    """List submodel descriptors for a shell descriptor."""
    aas_id = _decode_aas_id(aas_id_b64)
    svc = BuiltInRegistryService(db)
    record = await svc.get_shell_descriptor(tenant.tenant_id, aas_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shell descriptor not found",
        )

    results: list[SubmodelDescriptorResponse] = []
    for sm in record.submodel_descriptors:
        semantic_id = ""
        sem_id_obj = sm.get("semanticId", {})
        if isinstance(sem_id_obj, dict):
            keys = sem_id_obj.get("keys", [])
            if keys:
                semantic_id = keys[0].get("value", "")
        results.append(
            SubmodelDescriptorResponse(
                id=sm.get("id", ""),
                id_short=sm.get("idShort", ""),
                semantic_id=semantic_id,
                endpoints=sm.get("endpoints", []),
            )
        )
    return results


# ---- Search ----


@router.post("/search", response_model=list[ShellDescriptorResponse])
async def search_shell_descriptors(
    body: RegistrySearchRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> list[ShellDescriptorResponse]:
    """Search shell descriptors by asset ID key/value."""
    svc = BuiltInRegistryService(db)
    records = await svc.search_by_asset_id(tenant.tenant_id, body.asset_id_key, body.asset_id_value)
    return [_descriptor_to_response(r) for r in records]


# ---- Discovery ----


@router.post(
    "/discovery",
    response_model=AssetDiscoveryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_discovery_mapping(
    body: AssetDiscoveryCreate,
    db: DbSession,
    tenant: TenantPublisher,
) -> AssetDiscoveryResponse:
    """Create a discovery mapping (asset ID -> AAS ID)."""
    svc = DiscoveryService(db)
    mapping = await svc.create_mapping(
        tenant_id=tenant.tenant_id,
        asset_id_key=body.asset_id_key,
        asset_id_value=body.asset_id_value,
        aas_id=body.aas_id,
    )
    return AssetDiscoveryResponse(
        asset_id_key=mapping.asset_id_key,
        asset_id_value=mapping.asset_id_value,
        aas_id=mapping.aas_id,
    )


@router.get("/discovery", response_model=list[str])
async def lookup_discovery(
    db: DbSession,
    tenant: TenantPublisher,
    asset_id_key: str = Query(...),
    asset_id_value: str = Query(...),
) -> list[str]:
    """Look up AAS IDs by asset ID key/value pair."""
    svc = DiscoveryService(db)
    return await svc.lookup(tenant.tenant_id, asset_id_key, asset_id_value)
