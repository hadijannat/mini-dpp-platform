"""Public (unauthenticated) SMT editor endpoints."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import get_client_ip, get_redis
from app.db.session import DbSession
from app.modules.aas.conformance import validate_aas_environment
from app.modules.templates.instance_builder import TemplateInstanceBuilder
from app.modules.templates.router import (
    TemplateContractResponse,
    TemplateSourceMetadataResponse,
)
from app.modules.templates.service import TemplateRegistryService
from app.modules.units.enrichment import ensure_uom_concept_descriptions
from app.modules.units.payload import collect_uom_by_cd_id
from app.modules.units.registry import UomRegistryService, build_registry_indexes

logger = get_logger(__name__)
router = APIRouter()


class PublicTemplateSummary(BaseModel):
    template_key: str
    display_name: str
    catalog_status: str
    catalog_folder: str | None = None
    semantic_id: str
    latest_version: str
    fetched_at: str
    source_metadata: TemplateSourceMetadataResponse


class PublicTemplateListResponse(BaseModel):
    templates: list[PublicTemplateSummary]
    count: int
    status_filter: Literal["published", "deprecated", "all"]
    search: str | None = None


class PublicTemplateDetailResponse(BaseModel):
    template_key: str
    display_name: str
    catalog_status: str
    catalog_folder: str | None = None
    semantic_id: str
    latest_version: str
    fetched_at: str
    source_metadata: TemplateSourceMetadataResponse
    versions: list[dict[str, Any]] = Field(default_factory=list)


class PublicTemplateVersionsResponse(BaseModel):
    template_key: str
    versions: list[dict[str, Any]]
    count: int


class PublicPreviewRequest(BaseModel):
    template_key: str = Field(min_length=1, max_length=100)
    version: str | None = Field(default=None, max_length=20)
    data: dict[str, Any]


class PublicPreviewResponse(BaseModel):
    template_key: str
    version: str
    aas_environment: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class PublicExportRequest(PublicPreviewRequest):
    format: Literal["json", "aasx", "pdf"]


@dataclass
class PreparedPublicPreview:
    template: Any
    template_key: str
    version: str
    aas_environment: dict[str, Any]
    warnings: list[str]
    payload_size_bytes: int


async def _enrich_public_environment_uom(
    *,
    db: DbSession,
    template: Any,
    aas_environment: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    settings = get_settings()
    if not settings.uom_enrichment_enabled:
        return aas_environment, {"enabled": False}

    template_payload = (
        template.template_json_raw
        if isinstance(getattr(template, "template_json_raw", None), dict)
        else template.template_json
    )
    template_uom_by_cd_id = (
        collect_uom_by_cd_id(template_payload) if isinstance(template_payload, dict) else {}
    )
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
            logger.warning("public_smt_uom_registry_load_failed", error=str(exc))

    enriched, enrichment_stats = ensure_uom_concept_descriptions(
        aas_env=aas_environment,
        template_uom_by_cd_id=template_uom_by_cd_id,
        registry_by_cd_id=registry_by_cd_id,
        registry_by_specific_unit_id=registry_by_specific_unit_id,
        registry_by_symbol=registry_by_symbol,
    )
    return enriched, enrichment_stats


async def _apply_public_smt_rate_limit(
    *,
    request: Request,
    bucket: Literal["read", "export"],
) -> dict[str, str]:
    settings = get_settings()
    limit = (
        settings.public_smt_rate_limit_export_per_minute
        if bucket == "export"
        else settings.public_smt_rate_limit_read_per_minute
    )
    window_seconds = 60

    redis_client = await get_redis()
    if redis_client is None:
        return {}

    client_ip = get_client_ip(request)
    key = f"rl:public_smt:{bucket}:{client_ip}:{int(time.time()) // window_seconds}"

    try:
        pipeline = redis_client.pipeline()
        pipeline.incr(key)
        pipeline.expire(key, window_seconds)
        results: list[int | bool] = await pipeline.execute()
        current = int(results[0])
        remaining = max(0, limit - current)
    except Exception:
        logger.warning("public_smt_rate_limit_redis_error", client_ip=client_ip, bucket=bucket)
        return {}

    headers = {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(remaining),
    }
    if current > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={
                **headers,
                "Retry-After": str(window_seconds),
            },
        )
    return headers


def _sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", value)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-.")
    return cleaned or "sandbox-export"


def _allowed_id_short_pattern(template: str) -> re.Pattern[str]:
    escaped = re.escape(template)
    with_numeric_placeholders = re.sub(
        r"\\\{(0+)\\\}",
        lambda match: rf"\\d{{{len(match.group(1))}}}",
        escaped,
    )
    return re.compile(rf"^{with_numeric_placeholders}$")


def _naming_pattern_from_rule(rule: str | None) -> re.Pattern[str] | None:
    if not rule:
        return None
    normalized = rule.strip()
    if not normalized or normalized.lower() == "dynamic":
        return None
    if normalized.lower() == "idshort":
        return re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
    if normalized.startswith("regex:"):
        raw = normalized[len("regex:") :].strip()
        try:
            return re.compile(raw)
        except re.error:
            return None
    try:
        return re.compile(normalized)
    except re.error:
        return None


def _validate_dynamic_id_short_policy(
    *,
    schema: dict[str, Any] | None,
    data: Any,
    path: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    if schema is None:
        return []

    errors: list[dict[str, str]] = []
    schema_type = schema.get("type")

    if schema_type == "object":
        properties = schema.get("properties")
        properties_dict = properties if isinstance(properties, dict) else {}
        object_data = data if isinstance(data, dict) else {}

        declared_keys = set(properties_dict.keys())
        dynamic_keys = [key for key in object_data if key not in declared_keys]

        can_edit_id_short = schema.get("x-edit-id-short")
        allowed_id_short = schema.get("x-allowed-id-short")
        allowed_templates = (
            [value for value in allowed_id_short if isinstance(value, str)]
            if isinstance(allowed_id_short, list)
            else []
        )
        naming_rule = schema.get("x-naming") if isinstance(schema.get("x-naming"), str) else None

        if dynamic_keys:
            if can_edit_id_short is False:
                for key in dynamic_keys:
                    errors.append(
                        {
                            "path": ".".join([*path, key]),
                            "message": "Dynamic idShort keys are not editable for this field",
                        }
                    )
            else:
                if allowed_templates:
                    patterns = [
                        _allowed_id_short_pattern(template) for template in allowed_templates
                    ]
                    for key in dynamic_keys:
                        if not any(pattern.match(key) for pattern in patterns):
                            errors.append(
                                {
                                    "path": ".".join([*path, key]),
                                    "message": f"idShort '{key}' is not allowed",
                                }
                            )

                naming_pattern = _naming_pattern_from_rule(naming_rule)
                if naming_pattern is not None:
                    for key in dynamic_keys:
                        if not naming_pattern.match(key):
                            errors.append(
                                {
                                    "path": ".".join([*path, key]),
                                    "message": (
                                        f"idShort '{key}' violates naming rule '{naming_rule}'"
                                    ),
                                }
                            )

        for key, child_schema in properties_dict.items():
            if not isinstance(child_schema, dict):
                continue
            errors.extend(
                _validate_dynamic_id_short_policy(
                    schema=child_schema,
                    data=object_data.get(key),
                    path=(*path, key),
                )
            )

    if schema_type == "array":
        items = schema.get("items")
        if isinstance(items, dict) and isinstance(data, list):
            for idx, item in enumerate(data):
                errors.extend(
                    _validate_dynamic_id_short_policy(
                        schema=items,
                        data=item,
                        path=(*path, str(idx)),
                    )
                )

    return errors


def _validate_complexity_bounds(data: Any) -> None:
    settings = get_settings()

    try:
        serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Payload is not JSON serializable: {exc}",
        ) from exc

    payload_bytes = len(serialized.encode("utf-8"))
    if payload_bytes > settings.public_smt_payload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Payload too large: {payload_bytes} bytes "
                f"(max {settings.public_smt_payload_max_bytes})"
            ),
        )

    max_depth_seen = 0
    total_nodes_seen = 0

    def walk(node: Any, depth: int) -> None:
        nonlocal max_depth_seen, total_nodes_seen
        total_nodes_seen += 1
        max_depth_seen = max(max_depth_seen, depth)

        if depth > settings.public_smt_max_depth:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Payload exceeds max depth ({settings.public_smt_max_depth})",
            )
        if total_nodes_seen > settings.public_smt_max_total_nodes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Payload exceeds max nodes ({settings.public_smt_max_total_nodes})",
            )

        if isinstance(node, list):
            if len(node) > settings.public_smt_max_array_items:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Payload exceeds max array length ({settings.public_smt_max_array_items})"
                    ),
                )
            for item in node:
                walk(item, depth + 1)
        elif isinstance(node, dict):
            if len(node) > settings.public_smt_max_object_keys:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Payload exceeds max object keys ({settings.public_smt_max_object_keys})"
                    ),
                )
            for value in node.values():
                walk(value, depth + 1)

    walk(data, 1)


def _schema_validation_errors(schema: dict[str, Any], data: dict[str, Any]) -> list[dict[str, str]]:
    validator = Draft202012Validator(schema)
    errors: list[dict[str, str]] = []
    for error in validator.iter_errors(data):
        path = ".".join(str(part) for part in error.absolute_path)
        errors.append({"path": path or "root", "message": error.message})
    return errors


def _build_structured_instance_errors(exc: Exception) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    raw_errors = getattr(exc, "errors", None)
    if callable(raw_errors):
        try:
            extracted = raw_errors()
        except Exception:  # pragma: no cover - defensive path for third-party errors
            extracted = []
        if isinstance(extracted, list):
            for entry in extracted[:100]:
                if not isinstance(entry, dict):
                    continue
                loc = entry.get("loc")
                if isinstance(loc, (list, tuple)):
                    path = ".".join(str(part) for part in loc if part != "__root__") or "root"
                elif isinstance(loc, str):
                    path = loc or "root"
                else:
                    path = "root"
                message = str(entry.get("msg") or entry.get("message") or "").strip()
                if not message:
                    continue
                errors.append({"path": path, "message": message})

    if errors:
        return errors[:100]

    message = str(exc).strip() or exc.__class__.__name__
    exception_path = getattr(exc, "path", None)
    if isinstance(exception_path, (list, tuple)):
        path_value = ".".join(str(part) for part in exception_path) or "root"
    elif isinstance(exception_path, str):
        path_value = exception_path or "root"
    else:
        path_value = "root"
    return [{"path": path_value, "message": message}]


def _instance_failure_http_exception(*, code: str, message: str, exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": code,
            "message": message,
            "errors": _build_structured_instance_errors(exc),
        },
    )


def _log_instance_failure(
    request: Request | None,
    *,
    template_key: str,
    version: str | None,
    phase: str,
    exc: Exception,
) -> None:
    logger.warning(
        "public_smt_instance_build_failed",
        template_key=template_key,
        version=version,
        phase=phase,
        error_class=exc.__class__.__name__,
        request_id=request.headers.get("x-request-id") if request is not None else None,
        client_ip=get_client_ip(request) if request is not None else None,
    )


async def _prepare_preview(
    *,
    db: DbSession,
    payload: PublicPreviewRequest,
    request: Request | None = None,
) -> PreparedPublicPreview:
    service = TemplateRegistryService(db)
    template = await service.get_template(payload.template_key, payload.version)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{payload.template_key}' not found",
        )

    template_lookup = {row.template_key: row for row in await service.get_all_templates()}
    template_lookup.setdefault(template.template_key, template)
    contract = await service.generate_template_contract(
        template,
        template_lookup=template_lookup,
        strict_unknown_model_types=True,
    )
    schema = contract.get("schema")
    if not isinstance(schema, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Template schema unavailable",
        )

    _validate_complexity_bounds(payload.data)

    schema_errors = _schema_validation_errors(schema, payload.data)
    dynamic_key_errors = _validate_dynamic_id_short_policy(schema=schema, data=payload.data)
    all_errors = [*schema_errors, *dynamic_key_errors]
    if all_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "schema_validation_failed",
                "message": "Template data failed validation",
                "errors": all_errors[:100],
            },
        )

    builder = TemplateInstanceBuilder(service)
    try:
        aas_environment = builder.build_environment(
            template=template,
            data=payload.data,
            template_lookup=template_lookup,
        )
    except HTTPException:
        raise
    except Exception as exc:
        _log_instance_failure(
            request,
            template_key=payload.template_key,
            version=payload.version,
            phase="build_environment",
            exc=exc,
        )
        raise _instance_failure_http_exception(
            code="instance_build_failed",
            message="Unable to build AAS instance from provided template data",
            exc=exc,
        ) from exc

    validation = validate_aas_environment(aas_environment)
    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "metamodel_validation_failed",
                "message": "Generated AAS environment violates metamodel constraints",
                "errors": validation.errors,
                "warnings": validation.warnings,
            },
        )

    payload_size = len(
        json.dumps(payload.data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )

    return PreparedPublicPreview(
        template=template,
        template_key=template.template_key,
        version=template.idta_version,
        aas_environment=aas_environment,
        warnings=validation.warnings,
        payload_size_bytes=payload_size,
    )


def _to_public_template_summary(template: Any) -> PublicTemplateSummary:
    settings = get_settings()
    source_metadata = {
        "resolved_version": template.resolved_version or template.idta_version,
        "source_repo_ref": template.source_repo_ref or settings.idta_templates_repo_ref,
        "source_file_path": template.source_file_path,
        "source_file_sha": template.source_file_sha,
        "source_kind": template.source_kind,
        "selection_strategy": template.selection_strategy,
        "source_url": template.source_url,
        "catalog_status": template.catalog_status,
        "catalog_folder": template.catalog_folder,
        "display_name": template.display_name,
    }
    return PublicTemplateSummary(
        template_key=template.template_key,
        display_name=template.display_name,
        catalog_status=template.catalog_status,
        catalog_folder=template.catalog_folder,
        semantic_id=template.semantic_id,
        latest_version=template.idta_version,
        fetched_at=template.fetched_at.isoformat(),
        source_metadata=TemplateSourceMetadataResponse(**source_metadata),
    )


@router.get("/templates", response_model=PublicTemplateListResponse)
async def list_public_templates(
    request: Request,
    response: Response,
    db: DbSession,
    status_filter: Literal["published", "deprecated", "all"] = Query("published", alias="status"),
    search: str | None = Query(default=None, max_length=120),
) -> PublicTemplateListResponse:
    headers = await _apply_public_smt_rate_limit(request=request, bucket="read")
    response.headers.update(headers)

    service = TemplateRegistryService(db)
    templates = await service.list_templates_public(status_filter=status_filter, search=search)
    summaries = [_to_public_template_summary(template) for template in templates]
    return PublicTemplateListResponse(
        templates=summaries,
        count=len(summaries),
        status_filter=status_filter,
        search=search,
    )


@router.get("/templates/{template_key}", response_model=PublicTemplateDetailResponse)
async def get_public_template(
    template_key: str,
    request: Request,
    response: Response,
    db: DbSession,
) -> PublicTemplateDetailResponse:
    headers = await _apply_public_smt_rate_limit(request=request, bucket="read")
    response.headers.update(headers)

    service = TemplateRegistryService(db)
    template = await service.get_template(template_key)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_key}' not found",
        )

    versions = await service.list_template_versions_public(template_key)
    summary = _to_public_template_summary(template)
    return PublicTemplateDetailResponse(
        template_key=summary.template_key,
        display_name=summary.display_name,
        catalog_status=summary.catalog_status,
        catalog_folder=summary.catalog_folder,
        semantic_id=summary.semantic_id,
        latest_version=summary.latest_version,
        fetched_at=summary.fetched_at,
        source_metadata=summary.source_metadata,
        versions=versions,
    )


@router.get("/templates/{template_key}/versions", response_model=PublicTemplateVersionsResponse)
async def list_public_template_versions(
    template_key: str,
    request: Request,
    response: Response,
    db: DbSession,
) -> PublicTemplateVersionsResponse:
    headers = await _apply_public_smt_rate_limit(request=request, bucket="read")
    response.headers.update(headers)

    service = TemplateRegistryService(db)
    versions = await service.list_template_versions_public(template_key)
    if not versions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_key}' not found",
        )
    return PublicTemplateVersionsResponse(
        template_key=template_key, versions=versions, count=len(versions)
    )


@router.get("/templates/{template_key}/contract", response_model=TemplateContractResponse)
async def get_public_template_contract(
    template_key: str,
    request: Request,
    response: Response,
    db: DbSession,
    version: str | None = Query(default=None, max_length=20),
) -> TemplateContractResponse:
    headers = await _apply_public_smt_rate_limit(request=request, bucket="read")
    response.headers.update(headers)

    service = TemplateRegistryService(db)
    template = await service.get_template(template_key, version)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_key}' not found",
        )

    template_lookup = {row.template_key: row for row in await service.get_all_templates()}
    template_lookup.setdefault(template.template_key, template)
    contract = await service.generate_template_contract(
        template,
        template_lookup=template_lookup,
        strict_unknown_model_types=True,
    )
    return TemplateContractResponse(
        template_key=template.template_key,
        idta_version=contract["idta_version"],
        semantic_id=contract["semantic_id"],
        definition=contract["definition"],
        schema_=contract["schema"],
        source_metadata=TemplateSourceMetadataResponse(**contract["source_metadata"]),
        dropin_resolution_report=contract.get("dropin_resolution_report", []),
        unsupported_nodes=contract.get("unsupported_nodes", []),
        doc_hints=contract.get("doc_hints", {}),
        uom_diagnostics=contract.get("uom_diagnostics", {}),
    )


@router.post("/preview", response_model=PublicPreviewResponse)
async def preview_public_template_instance(
    payload: PublicPreviewRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> PublicPreviewResponse:
    headers = await _apply_public_smt_rate_limit(request=request, bucket="read")
    response.headers.update(headers)

    prepared = await _prepare_preview(db=db, payload=payload, request=request)
    return PublicPreviewResponse(
        template_key=prepared.template_key,
        version=prepared.version,
        aas_environment=prepared.aas_environment,
        warnings=prepared.warnings,
    )


@router.post("/export")
async def export_public_template_instance(
    payload: PublicExportRequest,
    request: Request,
    db: DbSession,
) -> Response:
    rate_limit_headers = await _apply_public_smt_rate_limit(request=request, bucket="export")

    started = time.perf_counter()
    preview_payload = PublicPreviewRequest(
        template_key=payload.template_key,
        version=payload.version,
        data=payload.data,
    )
    prepared = await _prepare_preview(db=db, payload=preview_payload, request=request)

    service = TemplateRegistryService(db)
    builder = TemplateInstanceBuilder(service)
    export_environment = prepared.aas_environment
    if payload.format in {"json", "aasx"}:
        export_environment, _ = await _enrich_public_environment_uom(
            db=db,
            template=prepared.template,
            aas_environment=prepared.aas_environment,
        )

    extension = payload.format
    try:
        if payload.format == "json":
            content = builder.to_json_bytes(export_environment)
            media_type = "application/json"
        elif payload.format == "aasx":
            content = builder.to_aasx_bytes(
                prepared.aas_environment,
                data_json_override=export_environment,
            )
            media_type = "application/asset-administration-shell-package+xml"
        elif payload.format == "pdf":
            content = builder.to_pdf_bytes(
                prepared.aas_environment,
                template_key=prepared.template_key,
                version=prepared.version,
            )
            media_type = "application/pdf"
        else:  # pragma: no cover - guarded by request model
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported format: {payload.format}",
            )
    except HTTPException:
        raise
    except Exception as exc:
        _log_instance_failure(
            request,
            template_key=payload.template_key,
            version=payload.version,
            phase=f"serialize_{payload.format}",
            exc=exc,
        )
        raise _instance_failure_http_exception(
            code="instance_serialization_failed",
            message="Unable to build AAS instance from provided template data",
            exc=exc,
        ) from exc

    filename = _sanitize_filename(
        f"{prepared.template_key}-{prepared.version}.{extension}",
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "public_smt_export",
        template_key=prepared.template_key,
        version=prepared.version,
        export_format=payload.format,
        payload_size_bytes=prepared.payload_size_bytes,
        response_size_bytes=len(content),
        duration_ms=elapsed_ms,
        client_ip=get_client_ip(request),
        request_id=request.headers.get("x-request-id"),
    )

    headers = {
        **rate_limit_headers,
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return Response(content=content, media_type=media_type, headers=headers)
