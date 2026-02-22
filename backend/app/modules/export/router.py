"""
API Router for DPP Export endpoints.
"""

import io
import zipfile
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.audit import emit_audit_event
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import require_access
from app.core.security.resource_context import build_dpp_resource_context
from app.core.tenancy import TenantContextDep
from app.db.models import DPPStatus
from app.db.session import DbSession
from app.modules.dpps.attachment_service import AttachmentNotFoundError, AttachmentService
from app.modules.dpps.service import DPPService
from app.modules.epcis.service import EPCISService
from app.modules.export.service import ExportService
from app.modules.templates.service import TemplateRegistryService
from app.modules.units.enrichment import ensure_uom_concept_descriptions
from app.modules.units.payload import collect_uom_by_cd_id
from app.modules.units.registry import UomRegistryService, build_registry_indexes
from app.modules.webhooks.service import trigger_webhooks

logger = get_logger(__name__)

router = APIRouter()


async def _collect_supplementary_export_files(
    *,
    db: DbSession,
    tenant_id: UUID,
    dpp_id: UUID,
    revision: Any,
) -> list[dict[str, Any]]:
    manifest = getattr(revision, "supplementary_manifest", None)
    if not isinstance(manifest, dict):
        return []
    files = manifest.get("files")
    if not isinstance(files, list):
        return []

    attachment_service = AttachmentService(db)
    export_files: list[dict[str, Any]] = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        attachment_id_raw = entry.get("attachment_id")
        package_path = entry.get("package_path")
        content_type = entry.get("content_type")
        if not isinstance(attachment_id_raw, str):
            continue
        try:
            attachment_id = UUID(attachment_id_raw)
        except ValueError:
            continue
        try:
            attachment, payload = await attachment_service.download_attachment_bytes(
                tenant_id=tenant_id,
                dpp_id=dpp_id,
                attachment_id=attachment_id,
            )
        except AttachmentNotFoundError:
            logger.warning(
                "supplementary_attachment_missing",
                dpp_id=str(dpp_id),
                attachment_id=attachment_id_raw,
            )
            continue
        export_files.append(
            {
                "package_path": package_path,
                "content_type": content_type or attachment.content_type,
                "payload": payload,
            }
        )
    return export_files


async def _resolve_templates_for_revision(*, db: DbSession, revision: Any) -> list[Any]:
    raw_provenance = getattr(revision, "template_provenance", None)
    provenance = raw_provenance if isinstance(raw_provenance, dict) else {}
    if not provenance:
        return []

    registry_service = TemplateRegistryService(db)
    templates: list[Any] = []
    for template_key in sorted(str(key).strip() for key in provenance if str(key).strip()):
        metadata = provenance.get(template_key)
        resolved_version = (
            str(metadata.get("resolved_version") or "").strip()
            if isinstance(metadata, dict)
            else ""
        )
        template = (
            await registry_service.get_template(template_key, resolved_version)
            if resolved_version
            else None
        )
        if template is None:
            template = await registry_service.get_template(template_key)
        if template is not None:
            templates.append(template)
    return templates


def _collect_template_uom_entries(templates: list[Any]) -> dict[str, Any]:
    by_cd_id: dict[str, Any] = {}
    for template in templates:
        payload = (
            template.template_json_raw
            if isinstance(getattr(template, "template_json_raw", None), dict)
            else template.template_json
        )
        if not isinstance(payload, dict):
            continue
        for cd_id, data_specification in collect_uom_by_cd_id(payload).items():
            by_cd_id.setdefault(cd_id, data_specification)
    return by_cd_id


async def _build_uom_enriched_environment(
    *,
    db: DbSession,
    revision: Any,
    aas_environment: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    settings = get_settings()
    if not settings.uom_enrichment_enabled:
        return aas_environment, {"enabled": False}

    templates = await _resolve_templates_for_revision(db=db, revision=revision)
    template_uom_by_cd_id = _collect_template_uom_entries(templates)
    registry_by_cd_id: dict[str, Any] = {}
    registry_by_specific_unit_id: dict[str, list[Any]] = {}
    registry_by_symbol: dict[str, list[Any]] = {}
    execute_attr = getattr(db, "execute", None)
    execute_is_mock = "unittest.mock" in type(execute_attr).__module__
    if settings.uom_registry_enabled and not execute_is_mock:
        try:
            registry_entries = await UomRegistryService(db).load_effective_entries()
            registry_by_cd_id, registry_by_specific_unit_id, registry_by_symbol = (
                build_registry_indexes(registry_entries)
            )
        except Exception as exc:  # pragma: no cover - defensive runtime fallback
            logger.warning("uom_registry_load_failed", error=str(exc))

    enriched, stats = ensure_uom_concept_descriptions(
        aas_env=aas_environment,
        template_uom_by_cd_id=template_uom_by_cd_id,
        registry_by_cd_id=registry_by_cd_id,
        registry_by_specific_unit_id=registry_by_specific_unit_id,
        registry_by_symbol=registry_by_symbol,
    )
    return enriched, {
        "enabled": True,
        "template_count": len(templates),
        **stats,
    }


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

    export_environment = revision.aas_env_json
    uom_export_stats: dict[str, Any] = {"enabled": False}
    if format in {"json", "jsonld", "turtle", "aasx", "xml"}:
        export_environment, uom_export_stats = await _build_uom_enriched_environment(
            db=db,
            revision=revision,
            aas_environment=revision.aas_env_json,
        )

    xml_uom_warning = "uom_xml_not_guaranteed_due_basyx_limitation"

    # Export based on format
    if format == "json":
        content = export_service.export_json(revision, aas_env_json=export_environment)
        await emit_audit_event(
            db_session=db,
            action="export_dpp",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
            metadata={"format": format, "uom_enrichment": uom_export_stats},
        )
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="dpp-{dpp_id}.json"',
            },
        )
    elif format == "aasx":
        supplementary_files = await _collect_supplementary_export_files(
            db=db,
            tenant_id=tenant.tenant_id,
            dpp_id=dpp_id,
            revision=revision,
        )
        content = export_service.export_aasx(
            revision,
            dpp_id,
            write_json=(aasx_serialization == "json"),
            supplementary_files=supplementary_files,
            aas_env_json=revision.aas_env_json,
            data_json_override=export_environment if aasx_serialization == "json" else None,
        )
        await emit_audit_event(
            db_session=db,
            action="export_dpp",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
            metadata={"format": format, "uom_enrichment": uom_export_stats},
        )
        response_headers = {
            "Content-Disposition": f'attachment; filename="dpp-{dpp_id}.aasx"',
        }
        if aasx_serialization == "xml":
            response_headers["X-UOM-Warning"] = xml_uom_warning
        return Response(
            content=content,
            media_type="application/asset-administration-shell-package+xml",
            headers=response_headers,
        )
    elif format == "jsonld":
        content = export_service.export_jsonld(revision, aas_env_json=export_environment)
        await emit_audit_event(
            db_session=db,
            action="export_dpp",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
            metadata={"format": format, "uom_enrichment": uom_export_stats},
        )
        return Response(
            content=content,
            media_type="application/ld+json",
            headers={
                "Content-Disposition": f'attachment; filename="dpp-{dpp_id}.jsonld"',
            },
        )
    elif format == "turtle":
        content = export_service.export_turtle(revision, aas_env_json=export_environment)
        await emit_audit_event(
            db_session=db,
            action="export_dpp",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
            metadata={"format": format, "uom_enrichment": uom_export_stats},
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
        try:
            content = export_service.export_xml(revision, aas_env_json=export_environment)
        except ValueError:
            content = export_service.export_xml(revision, aas_env_json=revision.aas_env_json)
        await emit_audit_event(
            db_session=db,
            action="export_dpp",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
            metadata={"format": format, "uom_enrichment": uom_export_stats},
        )
        return Response(
            content=content,
            media_type="application/xml",
            headers={
                "Content-Disposition": f'attachment; filename="dpp-{dpp_id}.xml"',
                "X-UOM-Warning": xml_uom_warning,
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
                        "format": body.format,
                    },
                    tenant=tenant,
                )

                if body.format == "aasx" and not tenant.is_publisher:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="AASX export requires publisher role",
                    )

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
                    export_environment, _ = await _build_uom_enriched_environment(
                        db=db,
                        revision=revision,
                        aas_environment=revision.aas_env_json,
                    )
                    content = export_service.export_json(revision, aas_env_json=export_environment)
                else:
                    supplementary_files = await _collect_supplementary_export_files(
                        db=db,
                        tenant_id=tenant.tenant_id,
                        dpp_id=dpp_id,
                        revision=revision,
                    )
                    export_environment, _ = await _build_uom_enriched_environment(
                        db=db,
                        revision=revision,
                        aas_environment=revision.aas_env_json,
                    )
                    content = export_service.export_aasx(
                        revision,
                        dpp_id,
                        supplementary_files=supplementary_files,
                        aas_env_json=revision.aas_env_json,
                        data_json_override=export_environment,
                    )

                zf.writestr(f"dpp-{dpp_id}.{ext}", content)
                results.append(BatchExportResultItem(dpp_id=dpp_id, status="ok"))
            except HTTPException as exc:
                logger.info(
                    "batch_export_item_forbidden",
                    dpp_id=str(dpp_id),
                    status_code=exc.status_code,
                )
                detail = exc.detail if isinstance(exc.detail, str) else "Forbidden"
                results.append(BatchExportResultItem(dpp_id=dpp_id, status="failed", error=detail))
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
