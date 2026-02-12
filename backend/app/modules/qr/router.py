"""
API Router for QR Code and Data Carrier generation endpoints.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.core.security import require_access
from app.core.security.resource_context import build_dpp_resource_context
from app.core.tenancy import TenantContextDep
from app.db.models import DPPStatus
from app.db.session import DbSession
from app.modules.dpps.service import DPPService
from app.modules.qr.schemas import (
    CarrierFormat,
    CarrierRequest,
    GS1DigitalLinkResponse,
    IEC61406LinkResponse,
)
from app.modules.qr.service import QRCodeService

router = APIRouter()


def _legacy_asset_ids(asset_ids: dict[str, object] | None) -> dict[str, str]:
    if not asset_ids:
        return {}
    normalized: dict[str, str] = {}
    for key, value in asset_ids.items():
        if value is None:
            continue
        text = str(value).strip()
        if text:
            normalized[key] = text
    return normalized


def _legacy_serial_fallback(serial: str, dpp_id: UUID) -> str:
    normalized = serial.strip()
    if normalized:
        return normalized
    # Legacy compatibility wrappers must continue to work for records missing
    # explicit serialNumber values.
    return str(dpp_id).replace("-", "")[:12]


@router.get("/{dpp_id}", deprecated=True)
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

    # Check access via ABAC
    shared_with_current_user = await dpp_service.is_resource_shared_with_user(
        tenant_id=tenant.tenant_id,
        resource_type="dpp",
        resource_id=dpp.id,
        user_subject=tenant.user.sub,
    )
    await require_access(
        tenant.user,
        "read",
        build_dpp_resource_context(dpp, shared_with_current_user=shared_with_current_user),
        tenant=tenant,
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


@router.post(
    "/{dpp_id}/carrier",
    deprecated=True,
    responses={
        200: {
            "content": {
                "image/png": {},
                "image/svg+xml": {},
                "application/pdf": {},
            },
            "description": "Generated data carrier image",
        }
    },
)
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

    # Check access via ABAC
    shared_with_current_user = await dpp_service.is_resource_shared_with_user(
        tenant_id=tenant.tenant_id,
        resource_type="dpp",
        resource_id=dpp.id,
        user_subject=tenant.user.sub,
    )
    await require_access(
        tenant.user,
        "read",
        build_dpp_resource_context(dpp, shared_with_current_user=shared_with_current_user),
        tenant=tenant,
    )

    # Only generate carriers for published DPPs
    if dpp.status != DPPStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data carriers can only be generated for published DPPs",
        )

    # Determine URL based on format
    if request.format == CarrierFormat.GS1_QR:
        gtin, serial, _is_pseudo = qr_service.extract_gtin_from_asset_ids(
            _legacy_asset_ids(dpp.asset_ids)
        )
        serial = _legacy_serial_fallback(serial, dpp_id)
        try:
            carrier_url = qr_service.build_gs1_digital_link(gtin, serial)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e
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
    try:
        carrier_bytes = qr_service.generate_qr_code(
            dpp_url=carrier_url,
            format=request.output_type.value,
            size=request.size,
            foreground_color=request.foreground_color,
            background_color=request.background_color,
            include_text=request.include_text,
            text_label=text_label,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
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


@router.get("/{dpp_id}/gs1", response_model=GS1DigitalLinkResponse, deprecated=True)
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

    # Check access via ABAC
    shared_with_current_user = await dpp_service.is_resource_shared_with_user(
        tenant_id=tenant.tenant_id,
        resource_type="dpp",
        resource_id=dpp.id,
        user_subject=tenant.user.sub,
    )
    await require_access(
        tenant.user,
        "read",
        build_dpp_resource_context(dpp, shared_with_current_user=shared_with_current_user),
        tenant=tenant,
    )

    # Only generate GS1 links for published DPPs
    if dpp.status != DPPStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GS1 Digital Links can only be generated for published DPPs",
        )

    gtin, serial, is_pseudo_gtin = qr_service.extract_gtin_from_asset_ids(_legacy_asset_ids(dpp.asset_ids))
    serial = _legacy_serial_fallback(serial, dpp_id)
    try:
        digital_link = qr_service.build_gs1_digital_link(gtin, serial)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    resolver_url = digital_link.split("/01/", 1)[0]

    return GS1DigitalLinkResponse(
        dpp_id=dpp_id,
        digital_link=digital_link,
        gtin=gtin,
        serial=serial,
        resolver_url=resolver_url,
        is_pseudo_gtin=is_pseudo_gtin,
    )


@router.get("/{dpp_id}/iec61406", response_model=IEC61406LinkResponse, deprecated=True)
async def get_iec61406_link(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantContextDep,
) -> IEC61406LinkResponse:
    """Get the IEC 61406 identification link for a DPP.

    Returns a URL-based identification link per IEC 61406 that encodes
    the manufacturer part ID and serial number as query parameters.
    """
    dpp_service = DPPService(db)
    qr_service = QRCodeService()

    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    shared_with_current_user = await dpp_service.is_resource_shared_with_user(
        tenant_id=tenant.tenant_id,
        resource_type="dpp",
        resource_id=dpp.id,
        user_subject=tenant.user.sub,
    )
    await require_access(
        tenant.user,
        "read",
        build_dpp_resource_context(dpp, shared_with_current_user=shared_with_current_user),
        tenant=tenant,
    )

    if dpp.status != DPPStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IEC 61406 links can only be generated for published DPPs",
        )

    asset_ids = dpp.asset_ids or {}
    base_url = qr_service.build_dpp_url(
        str(dpp_id), tenant_slug=tenant.tenant_slug, short_link=False
    )
    link = qr_service.build_iec61406_link(asset_ids, base_url)

    return IEC61406LinkResponse(
        dpp_id=dpp_id,
        identification_link=link,
        manufacturer_part_id=asset_ids.get("manufacturerPartId", ""),
        serial_number=asset_ids.get("serialNumber", ""),
    )
