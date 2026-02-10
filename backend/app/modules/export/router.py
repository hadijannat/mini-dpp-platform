"""
API Router for DPP Export endpoints.
"""

import io
import zipfile
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.audit import emit_audit_event
from app.core.logging import get_logger
from app.core.security import require_access
from app.core.security.resource_context import build_dpp_resource_context
from app.core.tenancy import TenantContextDep
from app.db.models import DPPStatus
from app.db.session import DbSession
from app.modules.dpps.service import DPPService
from app.modules.epcis.service import EPCISService
from app.modules.export.service import ExportService
from app.modules.webhooks.service import trigger_webhooks

logger = get_logger(__name__)

router = APIRouter()


@router.get("/{dpp_id}")
async def export_dpp(
    dpp_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantContextDep,
    format: Literal["json", "aasx", "pdf", "jsonld", "turtle", "xml"] = Query(
        "json", description="Export format"
    ),
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
    shared_with_current_user = await dpp_service.is_resource_shared_with_user(
        tenant_id=tenant.tenant_id,
        resource_type="dpp",
        resource_id=dpp.id,
        user_subject=tenant.user.sub,
    )

    await require_access(
        tenant.user,
        "export",
        {
            **build_dpp_resource_context(
                dpp,
                shared_with_current_user=shared_with_current_user,
            ),
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

    # Inject EPCIS Traceability submodel (if events exist for this DPP)
    epcis_service = EPCISService(db)
    epcis_events = await epcis_service.get_for_dpp(tenant.tenant_id, dpp_id, limit=100)
    if epcis_events:
        epcis_endpoint_url = (
            str(request.base_url).rstrip("/")
            + f"/api/v1/public/{tenant.tenant_slug}/epcis/events/{dpp_id}"
        )
        export_service.inject_traceability_submodel(
            revision,
            epcis_events,
            epcis_endpoint_url=epcis_endpoint_url,
        )

    # Notify webhooks
    await trigger_webhooks(
        db,
        tenant.tenant_id,
        "DPP_EXPORTED",
        {
            "event": "DPP_EXPORTED",
            "dpp_id": str(dpp_id),
            "format": format,
        },
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
    elif format == "jsonld":
        content = export_service.export_jsonld(revision)
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
            media_type="application/ld+json",
            headers={
                "Content-Disposition": f'attachment; filename="dpp-{dpp_id}.jsonld"',
            },
        )
    elif format == "turtle":
        content = export_service.export_turtle(revision)
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
            media_type="text/turtle",
            headers={
                "Content-Disposition": f'attachment; filename="dpp-{dpp_id}.ttl"',
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
    elif format == "xml":
        content = export_service.export_xml(revision)
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
            media_type="application/xml",
            headers={
                "Content-Disposition": f'attachment; filename="dpp-{dpp_id}.xml"',
            },
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format: {format}",
        )


class BatchExportRequest(BaseModel):
    dpp_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    format: Literal["json", "aasx"] = "json"


class BatchExportResultItem(BaseModel):
    dpp_id: UUID
    status: str
    error: str | None = None


class BatchExportResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[BatchExportResultItem]


@router.post("/batch")
async def batch_export(
    body: BatchExportRequest,
    request: Request,
    db: DbSession,
    tenant: TenantContextDep,
) -> Response:
    """Export multiple DPPs as a ZIP archive."""
    dpp_service = DPPService(db)
    export_service = ExportService()
    epcis_service = EPCISService(db)
    buffer = io.BytesIO()
    results: list[BatchExportResultItem] = []
    ext = "json" if body.format == "json" else "aasx"

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for dpp_id in body.dpp_ids:
            try:
                dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
                if not dpp:
                    results.append(
                        BatchExportResultItem(dpp_id=dpp_id, status="failed", error="Not found")
                    )
                    continue

                if dpp.status == DPPStatus.PUBLISHED:
                    revision = await dpp_service.get_published_revision(dpp_id, tenant.tenant_id)
                else:
                    revision = await dpp_service.get_latest_revision(dpp_id, tenant.tenant_id)

                if not revision:
                    results.append(
                        BatchExportResultItem(
                            dpp_id=dpp_id, status="failed", error="No revision found"
                        )
                    )
                    continue

                # Inject EPCIS if available
                epcis_events = await epcis_service.get_for_dpp(tenant.tenant_id, dpp_id, limit=100)
                if epcis_events:
                    epcis_url = (
                        str(request.base_url).rstrip("/")
                        + f"/api/v1/public/{tenant.tenant_slug}/epcis/events/{dpp_id}"
                    )
                    export_service.inject_traceability_submodel(
                        revision, epcis_events, epcis_endpoint_url=epcis_url
                    )

                if body.format == "json":
                    content = export_service.export_json(revision)
                else:
                    content = export_service.export_aasx(revision, dpp_id)

                zf.writestr(f"dpp-{dpp_id}.{ext}", content)
                results.append(BatchExportResultItem(dpp_id=dpp_id, status="ok"))
            except Exception:
                logger.warning("batch_export_item_failed", dpp_id=str(dpp_id), exc_info=True)
                results.append(
                    BatchExportResultItem(dpp_id=dpp_id, status="failed", error="Export failed")
                )

    succeeded = sum(1 for r in results if r.status == "ok")
    failed = len(results) - succeeded

    await emit_audit_event(
        db_session=db,
        action="batch_export",
        resource_type="dpp",
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"format": body.format, "total": len(body.dpp_ids), "succeeded": succeeded},
    )

    buffer.seek(0)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="dpp-batch-export.zip"',
            "X-Batch-Total": str(len(results)),
            "X-Batch-Succeeded": str(succeeded),
            "X-Batch-Failed": str(failed),
        },
    )
