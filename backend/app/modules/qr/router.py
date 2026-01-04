"""
API Router for QR Code generation endpoints.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.db.models import DPPStatus
from app.db.session import DbSession
from app.modules.dpps.service import DPPService
from app.modules.qr.service import QRCodeService

router = APIRouter()


@router.get("/{dpp_id}")
async def generate_qr_code(
    dpp_id: UUID,
    db: DbSession,
    format: Literal["png", "svg"] = Query("png", description="Image format"),
    size: int = Query(400, ge=100, le=1000, description="Image size in pixels"),
) -> Response:
    """
    Generate a QR code for a DPP.

    The QR code contains the DPP viewer URL for product identification.
    """
    dpp_service = DPPService(db)
    qr_service = QRCodeService()

    # Get DPP
    dpp = await dpp_service.get_dpp(dpp_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    # Only generate QR for published DPPs
    if dpp.status != DPPStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QR codes can only be generated for published DPPs",
        )

    # Build URL and generate QR
    dpp_url = qr_service.build_dpp_url(str(dpp_id))
    qr_bytes = qr_service.generate_qr_code(
        dpp_url=dpp_url,
        format=format,
        size=size,
    )

    # Return QR image
    if format == "png":
        return Response(
            content=qr_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": f'inline; filename="qr-{dpp_id}.png"',
            },
        )
    else:
        return Response(
            content=qr_bytes,
            media_type="image/svg+xml",
            headers={
                "Content-Disposition": f'inline; filename="qr-{dpp_id}.svg"',
            },
        )
