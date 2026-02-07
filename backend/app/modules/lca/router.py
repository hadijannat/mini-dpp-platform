"""API router for LCA / Product Carbon Footprint calculation endpoints.

All endpoints require publisher role and tenant context.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from app.core.audit import emit_audit_event
from app.core.security import require_access
from app.core.tenancy import TenantPublisher
from app.db.session import DbSession
from app.modules.dpps.service import DPPService
from app.modules.lca.schemas import ComparisonReport, ComparisonRequest, LCAReport, LCAScope
from app.modules.lca.service import LCAService

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dpp_resource(dpp_id: UUID, owner_subject: str) -> dict[str, str]:
    """Build an ABAC resource context dict for a DPP."""
    return {"type": "dpp", "id": str(dpp_id), "owner_subject": owner_subject}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/calculate/{dpp_id}",
    response_model=LCAReport,
    status_code=status.HTTP_200_OK,
)
async def calculate_pcf(
    dpp_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
    scope: LCAScope | None = None,
) -> LCAReport:
    """Calculate the Product Carbon Footprint for a DPP.

    Extracts the material inventory from the DPP's latest AAS
    environment and computes the GWP using the emission factor
    database. Results are persisted for future retrieval.
    """
    dpp_service = DPPService(db)
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    await require_access(
        tenant.user,
        "read",
        _dpp_resource(dpp.id, dpp.owner_subject),
        tenant=tenant,
    )

    lca_service = LCAService(db)
    try:
        report = await lca_service.calculate_dpp_pcf(
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            scope=scope,
            created_by=tenant.user.sub,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await emit_audit_event(
        db_session=db,
        action="lca_calculate",
        resource_type="dpp",
        resource_id=dpp_id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={
            "scope": report.scope,
            "total_gwp_kg_co2e": report.total_gwp_kg_co2e,
            "materials_count": len(report.material_inventory.items),
        },
    )

    return report


@router.get(
    "/report/{dpp_id}",
    response_model=LCAReport,
)
async def get_report(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> LCAReport:
    """Get the latest LCA calculation report for a DPP."""
    dpp_service = DPPService(db)
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    await require_access(
        tenant.user,
        "read",
        _dpp_resource(dpp.id, dpp.owner_subject),
        tenant=tenant,
    )

    lca_service = LCAService(db)
    report = await lca_service.get_latest_report(
        dpp_id=dpp_id,
        tenant_id=tenant.tenant_id,
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No LCA report found for DPP {dpp_id}",
        )

    return report


@router.post(
    "/compare",
    response_model=ComparisonReport,
)
async def compare_revisions(
    body: ComparisonRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> ComparisonReport:
    """Compare PCF calculations between two DPP revisions."""
    dpp_service = DPPService(db)
    dpp = await dpp_service.get_dpp(body.dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {body.dpp_id} not found",
        )

    await require_access(
        tenant.user,
        "read",
        _dpp_resource(dpp.id, dpp.owner_subject),
        tenant=tenant,
    )

    lca_service = LCAService(db)
    try:
        comparison = await lca_service.compare_revisions(
            dpp_id=body.dpp_id,
            tenant_id=tenant.tenant_id,
            rev_a=body.revision_a,
            rev_b=body.revision_b,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return comparison
