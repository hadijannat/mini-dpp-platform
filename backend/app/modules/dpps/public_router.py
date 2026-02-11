"""
Public (unauthenticated) API for reading published Digital Product Passports.

EU ESPR requires published DPPs to be accessible without authentication.
Only DPPs with status=PUBLISHED are served; drafts/archived return 404.
"""

from __future__ import annotations

import base64
import copy
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.db.models import DPP, DPPRevision, DPPStatus, EPCISEvent, Tenant, TenantStatus
from app.db.session import DbSession
from app.modules.dpps.idta_schemas import (
    PagedResult,
    PagingMetadata,
    ServiceDescription,
)
from app.modules.dpps.repository import AASRepositoryService
from app.modules.dpps.submodel_filter import filter_aas_env_by_espr_tier

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


def _normalize_public_key(key: str) -> str:
    return "".join(ch for ch in key.lower() if ch.isalnum())


def _is_sensitive_public_key(key: str) -> bool:
    return _normalize_public_key(key) in _SENSITIVE_PUBLIC_KEYS


def _is_sensitive_asset_id_key(key: str) -> bool:
    return _normalize_public_key(key) in _SENSITIVE_ASSET_ID_KEYS


def _filter_public_aas_environment(aas_env: dict[str, Any]) -> dict[str, Any]:
    """Remove non-public and sensitive fields from AAS env for unauthenticated access.

    Filtering is recursive:
    - Drops any AAS element marked with ``Confidentiality`` qualifier != ``public``
    - Removes known sensitive keys from nested dict structures
    """
    filtered = copy.deepcopy(aas_env)
    projected = _filter_public_node(filtered)
    if isinstance(projected, dict):
        return projected
    return {"submodels": []}


def _is_aas_element(node: dict[str, Any]) -> bool:
    return "modelType" in node or "idShort" in node or "qualifiers" in node


def _filter_public_node(node: Any) -> Any:
    """Recursively filter nested AAS structures for unauthenticated responses."""
    if isinstance(node, list):
        result: list[Any] = []
        for item in node:
            filtered_item = _filter_public_node(item)
            if filtered_item is None:
                continue
            result.append(filtered_item)
        return result

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


def _element_is_public(element: dict[str, Any]) -> bool:
    """Check if an element's confidentiality qualifiers allow public access."""
    qualifiers = element.get("qualifiers", [])
    for q in qualifiers:
        if q.get("type") == "Confidentiality":
            return str(q.get("value", "public")).lower() == "public"
    return True


def _filter_public_asset_ids(asset_ids: dict[str, Any]) -> dict[str, Any]:
    """Strip sensitive product-level identifiers from public asset ID maps."""
    return {key: value for key, value in asset_ids.items() if not _is_sensitive_asset_id_key(key)}


router = APIRouter()
LANDING_REFRESH_SLA_SECONDS = 30
LANDING_SUMMARY_CACHE_CONTROL = "public, max-age=15, stale-while-revalidate=15"


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


class PublicLandingSummaryResponse(BaseModel):
    """Public aggregate metrics for the landing page.

    The response is intentionally aggregate-only and excludes record-level fields.
    """

    tenant_slug: str
    published_dpps: int
    active_product_families: int
    dpps_with_traceability: int
    latest_publish_at: str | None
    generated_at: str
    scope: str | None = None
    refresh_sla_seconds: int | None = None


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


async def _load_public_landing_summary(
    db: DbSession,
    tenant_id: UUID | None,
    tenant_slug: str,
    scope: Literal["default", "all"] | None = None,
) -> PublicLandingSummaryResponse:
    """Compute public aggregate metrics for landing page consumption."""
    if tenant_id is not None:
        published_count_stmt = select(func.count(DPP.id)).where(
            DPP.tenant_id == tenant_id,
            DPP.status == DPPStatus.PUBLISHED,
        )
    else:
        published_count_stmt = (
            select(func.count(DPP.id))
            .select_from(DPP)
            .join(Tenant, DPP.tenant_id == Tenant.id)
            .where(
                DPP.status == DPPStatus.PUBLISHED,
                Tenant.status == TenantStatus.ACTIVE,
            )
        )
    published_count_result = await db.execute(published_count_stmt)
    published_dpps = int(published_count_result.scalar_one() or 0)

    if tenant_id is not None:
        families_stmt = select(
            func.count(func.distinct(DPP.asset_ids["manufacturerPartId"].astext))
        ).where(
            DPP.tenant_id == tenant_id,
            DPP.status == DPPStatus.PUBLISHED,
            DPP.asset_ids["manufacturerPartId"].astext.is_not(None),
            DPP.asset_ids["manufacturerPartId"].astext != "",
        )
    else:
        families_stmt = (
            select(func.count(func.distinct(DPP.asset_ids["manufacturerPartId"].astext)))
            .select_from(DPP)
            .join(Tenant, DPP.tenant_id == Tenant.id)
            .where(
                DPP.status == DPPStatus.PUBLISHED,
                Tenant.status == TenantStatus.ACTIVE,
                DPP.asset_ids["manufacturerPartId"].astext.is_not(None),
                DPP.asset_ids["manufacturerPartId"].astext != "",
            )
        )
    families_result = await db.execute(families_stmt)
    active_product_families = int(families_result.scalar_one() or 0)

    traceability_stmt = (
        select(func.count(func.distinct(EPCISEvent.dpp_id)))
        .select_from(EPCISEvent)
        .join(
            DPP,
            (DPP.id == EPCISEvent.dpp_id) & (DPP.tenant_id == EPCISEvent.tenant_id),
        )
        .where(DPP.status == DPPStatus.PUBLISHED)
    )
    if tenant_id is not None:
        traceability_stmt = traceability_stmt.where(EPCISEvent.tenant_id == tenant_id)
    else:
        traceability_stmt = traceability_stmt.join(Tenant, DPP.tenant_id == Tenant.id).where(
            Tenant.status == TenantStatus.ACTIVE
        )
    traceability_result = await db.execute(traceability_stmt)
    dpps_with_traceability = int(traceability_result.scalar_one() or 0)

    if tenant_id is not None:
        latest_publish_stmt = select(func.max(DPP.updated_at)).where(
            DPP.tenant_id == tenant_id,
            DPP.status == DPPStatus.PUBLISHED,
        )
    else:
        latest_publish_stmt = (
            select(func.max(DPP.updated_at))
            .select_from(DPP)
            .join(Tenant, DPP.tenant_id == Tenant.id)
            .where(
                DPP.status == DPPStatus.PUBLISHED,
                Tenant.status == TenantStatus.ACTIVE,
            )
        )
    latest_publish_result = await db.execute(latest_publish_stmt)
    latest_publish_dt = latest_publish_result.scalar_one()

    return PublicLandingSummaryResponse(
        tenant_slug=tenant_slug,
        published_dpps=published_dpps,
        active_product_families=active_product_families,
        dpps_with_traceability=dpps_with_traceability,
        latest_publish_at=latest_publish_dt.isoformat() if latest_publish_dt else None,
        generated_at=datetime.now(UTC).isoformat(),
        scope=scope,
        refresh_sla_seconds=LANDING_REFRESH_SLA_SECONDS,
    )


def _attach_landing_summary_observability_headers(
    response: Response,
    summary: PublicLandingSummaryResponse,
    request_started_at: datetime,
) -> None:
    elapsed_ms = max(
        0,
        int((datetime.now(UTC) - request_started_at).total_seconds() * 1_000),
    )
    response.headers["Server-Timing"] = f"landing_summary;dur={elapsed_ms}"

    latest_publish = summary.latest_publish_at
    if latest_publish:
        try:
            generated_at_dt = datetime.fromisoformat(summary.generated_at)
            latest_publish_dt = datetime.fromisoformat(latest_publish)
        except ValueError:
            return

        if generated_at_dt.tzinfo is None:
            generated_at_dt = generated_at_dt.replace(tzinfo=UTC)
        if latest_publish_dt.tzinfo is None:
            latest_publish_dt = latest_publish_dt.replace(tzinfo=UTC)

        freshness_age_seconds = max(
            0,
            int(
                (
                    generated_at_dt.astimezone(UTC) - latest_publish_dt.astimezone(UTC)
                ).total_seconds()
            ),
        )
        response.headers["X-Landing-Freshness-Age-Seconds"] = str(freshness_age_seconds)


@router.get(
    "/landing/summary",
    response_model=PublicLandingSummaryResponse,
)
async def get_public_scoped_landing_summary(
    db: DbSession,
    response: Response,
    scope: Literal["default", "all"] = Query(default="all"),
) -> PublicLandingSummaryResponse:
    """Public aggregate-only metrics for landing page trust strip with scope support."""
    request_started_at = datetime.now(UTC)
    if scope == "default":
        tenant = await _resolve_tenant(db, "default")
        summary = await _load_public_landing_summary(
            db,
            tenant.id,
            tenant.slug,
            scope=scope,
        )
    else:
        summary = await _load_public_landing_summary(
            db,
            tenant_id=None,
            tenant_slug="all",
            scope=scope,
        )

    response.headers["Cache-Control"] = LANDING_SUMMARY_CACHE_CONTROL
    _attach_landing_summary_observability_headers(response, summary, request_started_at)
    return summary


@router.get(
    "/{tenant_slug}/landing/summary",
    response_model=PublicLandingSummaryResponse,
)
async def get_public_landing_summary(
    tenant_slug: str,
    db: DbSession,
    response: Response,
) -> PublicLandingSummaryResponse:
    """Public aggregate-only metrics for landing page trust strip."""
    request_started_at = datetime.now(UTC)
    tenant = await _resolve_tenant(db, tenant_slug)
    response.headers["Cache-Control"] = LANDING_SUMMARY_CACHE_CONTROL
    summary = await _load_public_landing_summary(
        db,
        tenant.id,
        tenant.slug,
        scope="default" if tenant.slug == "default" else None,
    )
    _attach_landing_summary_observability_headers(response, summary, request_started_at)
    return summary


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
        asset_ids=_filter_public_asset_ids(dpp.asset_ids),
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
        asset_ids=_filter_public_asset_ids(dpp.asset_ids),
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
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64url-encoded identifier",
        )


SSP_002 = (
    "https://admin-shell.io/aas/API/3/0"
    "/AssetAdministrationShellRepositoryServiceSpecification/SSP-002"
)


@router.get("/{tenant_slug}/service-description")
async def get_service_description(
    tenant_slug: str,
    db: DbSession,
) -> ServiceDescription:
    """IDTA-01002 $metadata -- service description for this tenant."""
    await _resolve_tenant(db, tenant_slug)
    return ServiceDescription(profiles=[SSP_002])


@router.get("/{tenant_slug}/shells")
async def list_shells(
    tenant_slug: str,
    db: DbSession,
    limit: int = Query(default=10, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> PagedResult[PublicDPPResponse]:
    """List all published shells with cursor-based pagination."""
    tenant = await _resolve_tenant(db, tenant_slug)
    repo = AASRepositoryService(db)
    dpps, next_cursor = await repo.list_published_shells(tenant.id, cursor, limit)

    revisions_by_id = await repo.get_published_revisions_batch(dpps)

    items: list[PublicDPPResponse] = []
    for dpp in dpps:
        revision = revisions_by_id.get(dpp.current_published_revision_id)  # type: ignore[arg-type]
        aas_env: dict[str, Any] | None = None
        if revision:
            aas_env = _filter_public_aas_environment(revision.aas_env_json)
        items.append(
            PublicDPPResponse(
                id=dpp.id,
                status=dpp.status.value,
                asset_ids=_filter_public_asset_ids(dpp.asset_ids),
                created_at=dpp.created_at.isoformat(),
                updated_at=dpp.updated_at.isoformat(),
                current_revision_no=(revision.revision_no if revision else None),
                aas_environment=aas_env,
                digest_sha256=(revision.digest_sha256 if revision else None),
            )
        )

    return PagedResult[PublicDPPResponse](
        result=items,
        paging_metadata=PagingMetadata(cursor=next_cursor),
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
        asset_ids=_filter_public_asset_ids(dpp.asset_ids),
        created_at=dpp.created_at.isoformat(),
        updated_at=dpp.updated_at.isoformat(),
        current_revision_no=revision.revision_no if revision else None,
        aas_environment=aas_env,
        digest_sha256=revision.digest_sha256 if revision else None,
    )


@router.get(
    "/{tenant_slug}/shells/{aas_id_b64}/submodels",
)
async def list_submodel_refs(
    tenant_slug: str,
    aas_id_b64: str,
    db: DbSession,
    espr_tier: str | None = Query(default=None, alias="espr_tier"),
) -> list[dict[str, Any]]:
    """List submodel references (id + semanticId) for a shell."""
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
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    aas_env = _filter_public_aas_environment(revision.aas_env_json)
    aas_env = filter_aas_env_by_espr_tier(aas_env, espr_tier, in_place=True)

    refs: list[dict[str, Any]] = []
    for sm in aas_env.get("submodels", []):
        ref: dict[str, Any] = {"id": sm.get("id", "")}
        if "semanticId" in sm:
            ref["semanticId"] = sm["semanticId"]
        refs.append(ref)
    return refs


@router.get(
    "/{tenant_slug}/shells/{aas_id_b64}/submodels/{submodel_id_b64}",
)
async def get_submodel_by_id(
    tenant_slug: str,
    aas_id_b64: str,
    submodel_id_b64: str,
    db: DbSession,
    espr_tier: str | None = Query(default=None, alias="espr_tier"),
    content: Literal["normal", "value"] = Query(default="normal"),
) -> dict[str, Any]:
    """Get a specific submodel from a published DPP.

    Use ``?content=value`` to return only submodelElements (same as
    the ``/$value`` path suffix).
    """
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
    aas_env = filter_aas_env_by_espr_tier(aas_env, espr_tier, in_place=True)

    submodel = repo.get_submodel_from_revision(aas_env, submodel_id)
    if not submodel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submodel not found",
        )

    if content == "value":
        return {"submodelElements": submodel.get("submodelElements", [])}
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
    aas_env = filter_aas_env_by_espr_tier(aas_env, espr_tier, in_place=True)

    submodel = repo.get_submodel_from_revision(aas_env, submodel_id)
    if not submodel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submodel not found",
        )

    return {"submodelElements": submodel.get("submodelElements", [])}
