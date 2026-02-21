"""Public (unauthenticated) CEN prEN 18222 read/search facade."""

from __future__ import annotations

import copy
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from app.db.models import DPP, DPPStatus, Tenant, TenantStatus
from app.db.session import DbSession
from app.modules.cen_api.schemas import CENDPPSearchResponse, CENPaging, CENPublicDPPResponse
from app.modules.cen_api.service import CENAPIError, CENAPINotFoundError, CENAPIService
from app.modules.dpps.service import DPPService
from app.standards.cen_pren import get_cen_profiles, standards_profile_header

router = APIRouter()

_SENSITIVE_PUBLIC_KEYS = frozenset(
    {
        "dppid",
        "aasid",
        "serialnumber",
        "batchid",
        "globalassetid",
        "payload",
        "readpoint",
        "bizlocation",
        "ownersubject",
        "usersubject",
        "createdbysubject",
        "email",
    }
)

_SENSITIVE_ASSET_ID_KEYS = frozenset({"serialnumber", "batchid", "globalassetid", "dppid", "aasid"})


def _set_standards_header(response: Response) -> None:
    response.headers["X-Standards-Profile"] = standards_profile_header(get_cen_profiles())


async def _resolve_tenant(db: DbSession, tenant_slug: str) -> Tenant:
    result = await db.execute(
        select(Tenant).where(
            Tenant.slug == tenant_slug.strip().lower(),
            Tenant.status == TenantStatus.ACTIVE,
        )
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return tenant


def _normalize_public_key(key: str) -> str:
    return "".join(ch for ch in key.lower() if ch.isalnum())


def _is_sensitive_public_key(key: str) -> bool:
    return _normalize_public_key(key) in _SENSITIVE_PUBLIC_KEYS


def _is_sensitive_asset_id_key(key: str) -> bool:
    return _normalize_public_key(key) in _SENSITIVE_ASSET_ID_KEYS


def _is_aas_element(node: dict[str, Any]) -> bool:
    return "modelType" in node or "idShort" in node or "qualifiers" in node


def _element_is_public(element: dict[str, Any]) -> bool:
    qualifiers = element.get("qualifiers", [])
    for qualifier in qualifiers:
        if qualifier.get("type") == "Confidentiality":
            return str(qualifier.get("value", "public")).lower() == "public"
    return True


def _filter_public_node(node: Any) -> Any:
    if isinstance(node, list):
        output: list[Any] = []
        for item in node:
            filtered = _filter_public_node(item)
            if filtered is None:
                continue
            output.append(filtered)
        return output

    if isinstance(node, dict):
        if _is_aas_element(node) and not _element_is_public(node):
            return None
        filtered_dict: dict[str, Any] = {}
        for key, value in node.items():
            if _is_sensitive_public_key(key):
                continue
            filtered_value = _filter_public_node(value)
            if filtered_value is None and isinstance(value, dict) and _is_aas_element(value):
                continue
            filtered_dict[key] = filtered_value
        return filtered_dict

    return node


def _filter_public_aas_environment(aas_env: dict[str, Any]) -> dict[str, Any]:
    projected = _filter_public_node(copy.deepcopy(aas_env))
    if isinstance(projected, dict):
        return projected
    return {"submodels": []}


def _filter_public_asset_ids(asset_ids: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in asset_ids.items() if not _is_sensitive_asset_id_key(key)}


async def _to_public_response(
    *,
    service: CENAPIService,
    dpp_service: DPPService,
    dpp: DPP,
) -> CENPublicDPPResponse:
    revision = await dpp_service.get_published_revision(dpp_id=dpp.id, tenant_id=dpp.tenant_id)
    aas_env = None
    if revision is not None:
        decrypted = await dpp_service.get_revision_aas_for_reader(revision)
        if isinstance(decrypted, dict):
            aas_env = _filter_public_aas_environment(decrypted)

    cen_payload = await service.to_cen_dpp_response(dpp)
    return CENPublicDPPResponse(
        id=dpp.id,
        status=dpp.status.value,
        asset_ids=_filter_public_asset_ids(dpp.asset_ids or {}),
        created_at=dpp.created_at,
        updated_at=dpp.updated_at,
        current_revision_no=revision.revision_no if revision else None,
        aas_environment=aas_env,
        digest_sha256=revision.digest_sha256 if revision else None,
        product_identifier=cen_payload.product_identifier,
        identifier_scheme=cen_payload.identifier_scheme,
        granularity=cen_payload.granularity,
    )


@router.get(
    "/{tenant_slug}/cen/dpps/{dpp_id:uuid}",
    response_model=CENPublicDPPResponse,
    operation_id="PublicReadDPPById",
)
async def public_read_dpp_by_id(
    tenant_slug: str,
    dpp_id: UUID,
    db: DbSession,
    response: Response,
) -> CENPublicDPPResponse:
    _set_standards_header(response)
    tenant = await _resolve_tenant(db, tenant_slug)
    service = CENAPIService(db)
    dpp_service = DPPService(db)
    try:
        dpp = await service.get_published_dpp(tenant_id=tenant.id, dpp_id=dpp_id)
    except CENAPINotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    return await _to_public_response(service=service, dpp_service=dpp_service, dpp=dpp)


@router.get(
    "/{tenant_slug}/cen/dpps",
    response_model=CENDPPSearchResponse,
    operation_id="PublicSearchDPPs",
)
async def public_search_dpps(
    tenant_slug: str,
    db: DbSession,
    response: Response,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    identifier: str | None = Query(default=None),
    scheme: str | None = Query(default=None),
) -> CENDPPSearchResponse:
    _set_standards_header(response)
    tenant = await _resolve_tenant(db, tenant_slug)
    service = CENAPIService(db)
    dpp_service = DPPService(db)
    try:
        dpps, next_cursor = await service.search_dpps(
            tenant_id=tenant.id,
            limit=limit,
            cursor=cursor,
            identifier=identifier,
            scheme=scheme,
            status=DPPStatus.PUBLISHED.value,
            published_only=True,
        )
    except CENAPIError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    items = [await _to_public_response(service=service, dpp_service=dpp_service, dpp=dpp) for dpp in dpps]
    return CENDPPSearchResponse(items=items, paging=CENPaging(cursor=next_cursor))
