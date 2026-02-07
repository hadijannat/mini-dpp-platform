"""API router for ESPR compliance checking endpoints.

All endpoints require publisher role and tenant context.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from app.core.audit import emit_audit_event
from app.core.security import require_access
from app.core.tenancy import TenantPublisher
from app.db.session import DbSession
from app.modules.compliance.schemas import (
    CategoryRuleset,
    ComplianceSummary,
    ComplianceViolation,
)
from app.modules.compliance.service import ComplianceService, _get_engine
from app.modules.dpps.service import DPPService

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ComplianceCheckResponse(BaseModel):
    """Response for a compliance check."""

    dpp_id: UUID
    category: str
    is_compliant: bool
    checked_at: str
    violations: list[ComplianceViolation]
    summary: ComplianceSummary


class AllRulesResponse(BaseModel):
    """Response listing all rule categories."""

    categories: list[str]
    rulesets: dict[str, CategoryRuleset]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def _dpp_resource(dpp_id: UUID, owner_subject: str) -> dict[str, str]:
    """Build an ABAC resource context dict for a DPP."""
    return {"type": "dpp", "id": str(dpp_id), "owner_subject": owner_subject}


@router.post(
    "/check/{dpp_id}",
    response_model=ComplianceCheckResponse,
    status_code=status.HTTP_200_OK,
)
async def check_compliance(
    dpp_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
    category: str | None = Query(
        None,
        description="Explicit product category override (battery, textile, electronic). "
        "If omitted, auto-detected from semantic IDs.",
    ),
) -> ComplianceCheckResponse:
    """Run a compliance check on a DPP.

    Evaluates the DPP's latest AAS environment against the applicable
    ESPR rule set. Returns violations grouped by severity.
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

    compliance_service = ComplianceService(db)
    try:
        report = await compliance_service.check_dpp(
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            category=category,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await emit_audit_event(
        db_session=db,
        action="compliance_check",
        resource_type="dpp",
        resource_id=dpp_id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={
            "category": report.category,
            "is_compliant": report.is_compliant,
            "critical_violations": report.summary.critical_violations,
        },
    )

    return ComplianceCheckResponse(
        dpp_id=dpp_id,
        category=report.category,
        is_compliant=report.is_compliant,
        checked_at=report.checked_at.isoformat(),
        violations=report.violations,
        summary=report.summary,
    )


@router.get(
    "/rules",
    response_model=AllRulesResponse,
)
async def list_all_rules(
    tenant: TenantPublisher,  # noqa: ARG001 — required for auth
) -> AllRulesResponse:
    """List all available compliance rules grouped by category."""
    engine = _get_engine()
    return AllRulesResponse(
        categories=engine.list_categories(),
        rulesets=engine.get_all_rules(),
    )


@router.get(
    "/rules/{category}",
    response_model=CategoryRuleset,
)
async def get_rules_for_category(
    category: str,
    tenant: TenantPublisher,  # noqa: ARG001 — required for auth
) -> CategoryRuleset:
    """Get compliance rules for a specific product category."""
    engine = _get_engine()
    ruleset = engine.get_category_ruleset(category)
    if ruleset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rules found for category '{category}'",
        )
    return ruleset


@router.get(
    "/report/{dpp_id}",
    response_model=ComplianceCheckResponse,
)
async def get_compliance_report(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
    category: str | None = Query(
        None,
        description="Explicit product category override",
    ),
) -> ComplianceCheckResponse:
    """Get the compliance report for a DPP.

    Runs a fresh compliance check against the DPP's current revision
    and returns the report. This is equivalent to POST /check/{dpp_id}
    but uses GET for convenience in dashboards and status polling.
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

    compliance_service = ComplianceService(db)
    try:
        report = await compliance_service.check_dpp(
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            category=category,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ComplianceCheckResponse(
        dpp_id=dpp_id,
        category=report.category,
        is_compliant=report.is_compliant,
        checked_at=report.checked_at.isoformat(),
        violations=report.violations,
        summary=report.summary,
    )
