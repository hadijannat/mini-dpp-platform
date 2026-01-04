"""
API Router for DPP Export endpoints.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.core.security import CurrentUser
from app.db.models import DPPStatus
from app.db.session import DbSession
from app.modules.dpps.service import DPPService
from app.modules.export.service import ExportService

router = APIRouter()


@router.get("/{dpp_id}")
async def export_dpp(
    dpp_id: UUID,
    db: DbSession,
    user: CurrentUser,
    format: Literal["json", "aasx", "pdf"] = Query("json", description="Export format"),
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
    dpp = await dpp_service.get_dpp(dpp_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    # Check access
    if dpp.status != DPPStatus.PUBLISHED and dpp.owner_subject != user.sub and not user.is_publisher:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # AASX export requires publisher role
    if format == "aasx" and not user.is_publisher:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AASX export requires publisher role",
        )

    # Get revision
    if dpp.status == DPPStatus.PUBLISHED:
        revision = await dpp_service.get_published_revision(dpp_id)
    else:
        revision = await dpp_service.get_latest_revision(dpp_id)

    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No revision found for DPP",
        )

    # Export based on format
    if format == "json":
        content = export_service.export_json(revision)
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="dpp-{dpp_id}.json"',
            },
        )
    elif format == "aasx":
        content = export_service.export_aasx(revision, dpp_id)
        return Response(
            content=content,
            media_type="application/asset-administration-shell-package+xml",
            headers={
                "Content-Disposition": f'attachment; filename="dpp-{dpp_id}.aasx"',
            },
        )
    elif format == "pdf":
        content = export_service.export_pdf(revision, dpp_id)
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
