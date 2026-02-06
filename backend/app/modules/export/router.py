"""
API Router for DPP Export endpoints.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response

from app.core.audit import emit_audit_event
from app.core.security import require_access
from app.core.tenancy import TenantContextDep
from app.db.models import DPPStatus
from app.db.session import DbSession
from app.modules.dpps.service import DPPService
from app.modules.export.service import ExportService

router = APIRouter()


@router.get("/{dpp_id}")
async def export_dpp(
    dpp_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantContextDep,
    format: Literal["json", "aasx", "pdf"] = Query("json", description="Export format"),
    aasx_serialization: Literal["json", "xml"] = Query(
        "json", description="Serialization format inside AASX package (json or xml)"
    ),
) -> Response:
    """
    Export a DPP in the specified format.

    Supported formats:
    - json: AAS Environment JSON with metadata
    - aasx: AASX package (IDTA Part 5 compliant)
    - pdf: PDF summary
    """
    dpp_service = DPPService(db)
    export_service = ExportService()

    # Get DPP
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    await require_access(
        tenant.user,
        "export",
        {
            "type": "dpp",
            "id": str(dpp.id),
            "owner_subject": dpp.owner_subject,
            "status": dpp.status.value,
            "format": format,
        },
        tenant=tenant,
    )

    # AASX export requires publisher role (explicit guard in addition to ABAC)
    if format == "aasx" and not tenant.is_publisher:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AASX export requires publisher role",
        )

    # Get revision
    if dpp.status == DPPStatus.PUBLISHED:
        revision = await dpp_service.get_published_revision(dpp_id, tenant.tenant_id)
    else:
        revision = await dpp_service.get_latest_revision(dpp_id, tenant.tenant_id)

    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No revision found for DPP",
        )

    # Export based on format
    if format == "json":
        content = export_service.export_json(revision)
        await emit_audit_event(
            db_session=db,
            action="export_dpp",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
            metadata={"format": format},
        )
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="dpp-{dpp_id}.json"',
            },
        )
    elif format == "aasx":
        content = export_service.export_aasx(
            revision, dpp_id, write_json=(aasx_serialization == "json")
        )
        await emit_audit_event(
            db_session=db,
            action="export_dpp",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
            metadata={"format": format},
        )
        return Response(
            content=content,
            media_type="application/asset-administration-shell-package+xml",
            headers={
                "Content-Disposition": f'attachment; filename="dpp-{dpp_id}.aasx"',
            },
        )
    elif format == "pdf":
        content = export_service.export_pdf(revision, dpp_id)
        await emit_audit_event(
            db_session=db,
            action="export_dpp",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
            metadata={"format": format},
        )
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="dpp-{dpp_id}.pdf"',
            },
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format: {format}",
        )
