"""
API Router for QR Code and Data Carrier generation endpoints.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.core.tenancy import TenantContextDep
from app.db.models import DPPStatus
from app.db.session import DbSession
from app.modules.dpps.service import DPPService
from app.modules.qr.schemas import (
    CarrierFormat,
    CarrierRequest,
    CarrierResponse,
    GS1DigitalLinkResponse,
)
from app.modules.qr.service import QRCodeService

router = APIRouter()


@router.get("/{dpp_id}")
async def generate_qr_code(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantContextDep,
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
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
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
    dpp_url = qr_service.build_dpp_url(
        str(dpp_id), tenant_slug=tenant.tenant_slug, short_link=False
    )
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


@router.post("/{dpp_id}/carrier", response_model=CarrierResponse)
async def generate_carrier(
    dpp_id: UUID,
    request: CarrierRequest,
    db: DbSession,
    tenant: TenantContextDep,
) -> Response:
    """
    Generate a customized data carrier for a DPP.

    Supports QR codes and GS1 Digital Link format with configurable
    colors, size, and output format (PNG, SVG, PDF).
    """
    dpp_service = DPPService(db)
    qr_service = QRCodeService()

    # Get DPP
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    # Determine URL based on format
    if request.format == CarrierFormat.GS1_QR:
        # Use GS1 Digital Link format
        gtin, serial = qr_service.extract_gtin_from_asset_ids(dpp.asset_ids or {})
        carrier_url = qr_service.build_gs1_digital_link(gtin, serial)
    else:
        # Standard DPP viewer URL
        carrier_url = qr_service.build_dpp_url(
            str(dpp_id), tenant_slug=tenant.tenant_slug, short_link=False
        )

    # Build text label if requested
    text_label = None
    if request.include_text:
        part_id = (dpp.asset_ids or {}).get("manufacturerPartId", str(dpp_id)[:8])
        text_label = f"DPP: {part_id}"

    # Generate carrier
    carrier_bytes = qr_service.generate_qr_code(
        dpp_url=carrier_url,
        format=request.output_type.value,
        size=request.size,
        foreground_color=request.foreground_color,
        background_color=request.background_color,
        include_text=request.include_text,
        text_label=text_label,
    )

    # Determine media type and filename
    media_types = {
        "png": "image/png",
        "svg": "image/svg+xml",
        "pdf": "application/pdf",
    }
    extensions = {"png": "png", "svg": "svg", "pdf": "pdf"}

    output = request.output_type.value
    return Response(
        content=carrier_bytes,
        media_type=media_types[output],
        headers={
            "Content-Disposition": f'inline; filename="carrier-{dpp_id}.{extensions[output]}"',
        },
    )


@router.get("/{dpp_id}/gs1", response_model=GS1DigitalLinkResponse)
async def get_gs1_digital_link(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantContextDep,
) -> GS1DigitalLinkResponse:
    """
    Get the GS1 Digital Link URL for a DPP.

    Returns the GS1 Digital Link format URL that can be encoded
    in a QR code for EU DPP/ESPR compliance.
    """
    dpp_service = DPPService(db)
    qr_service = QRCodeService()

    # Get DPP
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    # Extract GTIN and serial
    gtin, serial = qr_service.extract_gtin_from_asset_ids(dpp.asset_ids or {})

    # Build GS1 Digital Link
    resolver_url = qr_service.DEFAULT_GS1_RESOLVER
    digital_link = qr_service.build_gs1_digital_link(gtin, serial, resolver_url)

    return GS1DigitalLinkResponse(
        dpp_id=dpp_id,
        digital_link=digital_link,
        gtin=gtin,
        serial=serial,
        resolver_url=resolver_url,
    )
