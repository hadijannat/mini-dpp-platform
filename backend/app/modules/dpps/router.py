"""
API Router for DPP (Digital Product Passport) endpoints.
"""

import asyncio
import hashlib
import io
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, RootModel, field_validator
from sqlalchemy import text

from app.core.audit import emit_audit_event
from app.core.config import get_settings
from app.core.identifiers import IdentifierValidationError
from app.core.logging import get_logger
from app.core.security import require_access
from app.core.security.actor_metadata import actor_payload, load_users_by_subject
from app.core.security.resource_context import build_dpp_resource_context
from app.core.tenancy import TenantAdmin, TenantContext, TenantContextDep, TenantPublisher
from app.db.models import DPPStatus
from app.db.session import DbSession
from app.modules.aas.conformance import validate_aas_environment
from app.modules.digital_thread.handlers import record_lifecycle_event
from app.modules.dpps.aasx_ingest import AasxIngestService
from app.modules.dpps.attachment_service import AttachmentNotFoundError, AttachmentService
from app.modules.dpps.service import AmbiguousSubmodelBindingError, DPPService
from app.modules.epcis.handlers import record_epcis_lifecycle_event
from app.modules.masters.service import DPPMasterService
from app.modules.registry.handlers import auto_register_shell_descriptor
from app.modules.resolver.handlers import auto_register_resolver_links
from app.modules.templates.service import TemplateRegistryService
from app.modules.webhooks.service import trigger_webhooks

logger = get_logger(__name__)
router = APIRouter()
_refresh_rebuild_local_locks: dict[str, asyncio.Lock] = {}
_refresh_rebuild_local_locks_guard = asyncio.Lock()


def _can_view_drafts(dpp: Any, tenant: TenantContext, *, shared_with_current_user: bool) -> bool:
    return (
        dpp.owner_subject == tenant.user.sub or tenant.is_tenant_admin or shared_with_current_user
    )


async def _resolve_revision(
    service: DPPService,
    dpp: Any,
    tenant: TenantContext,
    *,
    shared_with_current_user: bool,
) -> Any | None:
    if dpp.status == DPPStatus.PUBLISHED and not _can_view_drafts(
        dpp,
        tenant,
        shared_with_current_user=shared_with_current_user,
    ):
        return await service.get_published_revision(dpp.id, tenant.tenant_id)
    return await service.get_latest_revision(dpp.id, tenant.tenant_id)


async def _read_upload_file_limited(file: UploadFile, *, max_bytes: int) -> bytes:
    """Read UploadFile in chunks and reject payloads exceeding the configured limit."""
    chunk_size = 1024 * 1024
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"AASX file exceeds maximum upload size ({max_bytes} bytes)",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _access_source(
    *,
    tenant: TenantContext,
    owner_subject: str,
    shared_with_current_user: bool,
) -> Literal["owner", "share", "tenant_admin"]:
    if tenant.is_tenant_admin and tenant.user.sub != owner_subject and not shared_with_current_user:
        return "tenant_admin"
    if shared_with_current_user and tenant.user.sub != owner_subject:
        return "share"
    return "owner"


@asynccontextmanager
async def _acquire_refresh_rebuild_guard(db: DbSession, dpp_id: UUID) -> AsyncIterator[None]:
    """
    Enforce one in-flight refresh+rebuild per DPP.

    Uses PostgreSQL transaction advisory lock when available.
    Falls back to in-process lock for non-Postgres test/dev backends.
    """
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        lock_result = await db.execute(
            text("SELECT pg_try_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"dpp:refresh-rebuild:{dpp_id}"},
        )
        acquired = bool(lock_result.scalar())
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A refresh and rebuild is already in progress for this DPP",
            )
        yield
        return

    lock_key = str(dpp_id)
    async with _refresh_rebuild_local_locks_guard:
        lock = _refresh_rebuild_local_locks.setdefault(lock_key, asyncio.Lock())
    if lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A refresh and rebuild is already in progress for this DPP",
        )
    await lock.acquire()
    try:
        yield
    finally:
        lock.release()
        if not lock.locked():
            async with _refresh_rebuild_local_locks_guard:
                existing = _refresh_rebuild_local_locks.get(lock_key)
                if existing is lock and not existing.locked():
                    _refresh_rebuild_local_locks.pop(lock_key, None)


class AssetIdsInput(BaseModel):
    """Input model for asset identifiers."""

    manufacturerPartId: str | None = None
    serialNumber: str | None = None
    batchId: str | None = None
    globalAssetId: str | None = None
    gtin: str | None = Field(
        default=None,
        description="GS1 GTIN (8/12/13/14 digits). Validated via check digit.",
    )

    @field_validator("gtin")
    @classmethod
    def validate_gtin_check_digit(cls, v: str | None) -> str | None:
        if v is None:
            return v
        from app.modules.qr.service import QRCodeService

        if not QRCodeService.validate_gtin(v):
            raise ValueError(f"GTIN '{v}' has an invalid check digit")
        return v


def _build_digital_link_uri(
    resolver_base_url: str,
    gtin: str,
    serial: str | None = None,
) -> str:
    """Build a canonical GS1 Digital Link URI."""
    base = resolver_base_url.rstrip("/")
    uri = f"{base}/01/{gtin}"
    if serial:
        uri += f"/21/{serial}"
    return uri


class CreateDPPRequest(BaseModel):
    """Request model for creating a new DPP."""

    asset_ids: AssetIdsInput
    selected_templates: list[str] = Field(
        default=["digital-nameplate"],
        description="List of template keys to include",
    )
    initial_data: dict[str, Any] | None = None
    required_specific_asset_ids: list[str] | None = None


class ImportDPPRequest(RootModel[dict[str, Any]]):
    """Request model for importing a DPP from JSON."""


class UpdateSubmodelRequest(BaseModel):
    """Request model for updating a submodel."""

    template_key: str
    data: dict[str, Any]
    rebuild_from_template: bool = False
    submodel_id: str | None = None


class SubmodelPatchOperation(BaseModel):
    """Atomic deterministic patch operation for submodel mutation."""

    op: Literal["set_value", "set_multilang", "add_list_item", "remove_list_item", "set_file_ref"]
    path: str
    value: Any | None = None
    index: int | None = None


class PatchSubmodelRequest(BaseModel):
    """Request model for canonical patch-based submodel updates."""

    template_key: str
    operations: list[SubmodelPatchOperation] = Field(default_factory=list)
    submodel_id: str | None = None
    base_revision_id: UUID | None = None
    strict: bool = True


class AttachmentUploadResponse(BaseModel):
    """Response payload for uploaded DPP attachments."""

    attachment_id: UUID
    content_type: str
    size_bytes: int
    url: str


class ActorSummary(BaseModel):
    """Actor identity summary for ownership and provenance fields."""

    subject: str
    display_name: str | None = None
    email_masked: str | None = None


class AccessSummary(BaseModel):
    """Current user's effective access to the resource."""

    can_read: bool
    can_update: bool
    can_publish: bool
    can_archive: bool
    source: Literal["owner", "share", "tenant_admin"]


class DPPResponse(BaseModel):
    """Response model for DPP data."""

    id: UUID
    status: str
    owner_subject: str
    visibility_scope: Literal["owner_team", "tenant"]
    owner: ActorSummary
    access: AccessSummary
    asset_ids: dict[str, Any]
    qr_payload: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SubmodelBindingResponse(BaseModel):
    """Resolved submodel->template binding metadata."""

    submodel_id: str | None = None
    id_short: str | None = None
    semantic_id: str | None = None
    normalized_semantic_id: str | None = None
    template_key: str | None = None
    binding_source: str
    idta_version: str | None = None
    resolved_version: str | None = None
    support_status: str | None = None
    refresh_enabled: bool | None = None


class DPPDetailResponse(DPPResponse):
    """Detailed response model including revision data."""

    current_revision_no: int | None
    aas_environment: dict[str, Any] | None
    digest_sha256: str | None
    submodel_bindings: list[SubmodelBindingResponse] = Field(default_factory=list)
    required_specific_asset_ids: list[str] = Field(default_factory=list)
    missing_required_specific_asset_ids: list[str] = Field(default_factory=list)
    publish_blockers: list[str] = Field(default_factory=list)


class DPPListResponse(BaseModel):
    """Response model for list of DPPs."""

    dpps: list[DPPResponse]
    count: int
    total_count: int
    limit: int
    offset: int


class RevisionResponse(BaseModel):
    """Response model for revision data."""

    id: UUID
    revision_no: int
    state: str
    digest_sha256: str
    created_by_subject: str
    created_at: str
    template_provenance: dict[str, Any] | None = None


class SubmodelDefinitionResponse(BaseModel):
    """Response model for submodel definition AST per revision."""

    dpp_id: UUID
    template_key: str
    revision_id: UUID
    revision_no: int
    state: str
    definition: dict[str, Any]


class BulkRebuildError(BaseModel):
    """Response model for rebuild errors."""

    dpp_id: UUID
    error: str


class BulkRebuildResponse(BaseModel):
    """Response model for bulk rebuild results."""

    total: int
    updated: int
    skipped: int
    errors: list[BulkRebuildError]


class RefreshRebuildFailure(BaseModel):
    """Single template/submodel refresh+rebuild failure entry."""

    template_key: str | None = None
    submodel_id: str | None = None
    submodel: str
    error: str


class RefreshRebuildSkipped(BaseModel):
    """Single skipped submodel refresh+rebuild entry."""

    submodel: str
    reason: str


class RefreshRebuildSuccess(BaseModel):
    """Single successful template/submodel refresh+rebuild entry."""

    template_key: str
    submodel_id: str
    submodel: str


class RefreshRebuildSubmodelsResponse(BaseModel):
    """Response for one-DPP template refresh + submodel rebuild run."""

    attempted: int
    succeeded: list[RefreshRebuildSuccess]
    failed: list[RefreshRebuildFailure]
    skipped: list[RefreshRebuildSkipped]


class RepairInvalidListsRequest(BaseModel):
    """Request model for tenant-level AASd-120 list-item repairs."""

    dry_run: bool = False
    dpp_ids: list[UUID] | None = None
    limit: int | None = Field(default=None, ge=1, le=5000)


class RepairInvalidListsError(BaseModel):
    """Per-DPP repair failure details."""

    dpp_id: UUID
    reason: str


class RepairInvalidListsStats(BaseModel):
    """Aggregate sanitizer stats for a repair run."""

    lists_scanned: int
    items_scanned: int
    idshort_removed: int
    paths_changed: int


class RepairInvalidListsResponse(BaseModel):
    """Summary response for AASd-120 repair endpoint."""

    total: int
    repaired: int
    skipped: int
    errors: list[RepairInvalidListsError]
    dry_run: bool
    stats: RepairInvalidListsStats


class BatchImportItem(BaseModel):
    """Single item in a batch import request."""

    asset_ids: AssetIdsInput
    selected_templates: list[str] = Field(default=["digital-nameplate"])
    initial_data: dict[str, Any] | None = None
    required_specific_asset_ids: list[str] | None = None


class BatchImportRequest(BaseModel):
    """Request model for batch DPP import."""

    dpps: list[BatchImportItem] = Field(..., min_length=1, max_length=100)


class BatchImportResultItem(BaseModel):
    """Result for a single batch import item."""

    index: int
    dpp_id: UUID | None = None
    status: str
    error: str | None = None


class BatchImportResponse(BaseModel):
    """Response model for batch import results."""

    job_id: UUID
    total: int
    succeeded: int
    failed: int
    results: list[BatchImportResultItem]


class BatchImportJobItemResponse(BaseModel):
    """Persisted batch import item result."""

    index: int
    dpp_id: UUID | None = None
    status: str
    error: str | None = None
    created_at: str


class BatchImportJobSummaryResponse(BaseModel):
    """Persisted batch import job summary row."""

    id: UUID
    requested_by_subject: str
    requested_by: ActorSummary
    total: int
    succeeded: int
    failed: int
    created_at: str


class BatchImportJobListResponse(BaseModel):
    """Paginated batch import job listing."""

    jobs: list[BatchImportJobSummaryResponse]
    count: int
    total_count: int
    limit: int
    offset: int


class BatchImportJobDetailResponse(BatchImportJobSummaryResponse):
    """Batch import job with per-item outcomes."""

    items: list[BatchImportJobItemResponse]


class DiffEntry(BaseModel):
    """Individual change between two revisions."""

    path: str
    operation: Literal["added", "removed", "changed"]
    old_value: Any | None = None
    new_value: Any | None = None


class DPPDiffResult(BaseModel):
    """Structured diff between two DPP revisions."""

    from_rev: int
    to_rev: int
    added: list[DiffEntry]
    removed: list[DiffEntry]
    changed: list[DiffEntry]


def _dpp_response_payload(
    dpp: Any,
    *,
    owner: dict[str, str | None],
    tenant: TenantContext,
    shared_with_current_user: bool,
) -> DPPResponse:
    is_owner = dpp.owner_subject == tenant.user.sub
    can_mutate = tenant.is_tenant_admin or is_owner
    return DPPResponse(
        id=dpp.id,
        status=dpp.status.value,
        owner_subject=dpp.owner_subject,
        visibility_scope=(
            dpp.visibility_scope.value
            if hasattr(dpp.visibility_scope, "value")
            else str(dpp.visibility_scope)
        ),
        owner=ActorSummary(**owner),
        access=AccessSummary(
            can_read=True,
            can_update=can_mutate,
            can_publish=can_mutate,
            can_archive=can_mutate,
            source=_access_source(
                tenant=tenant,
                owner_subject=dpp.owner_subject,
                shared_with_current_user=shared_with_current_user,
            ),
        ),
        asset_ids=dpp.asset_ids,
        qr_payload=dpp.qr_payload,
        created_at=dpp.created_at.isoformat(),
        updated_at=dpp.updated_at.isoformat(),
    )


@router.post("", response_model=DPPResponse, status_code=status.HTTP_201_CREATED)
async def create_dpp(
    body: CreateDPPRequest,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> DPPResponse:
    """
    Create a new Digital Product Passport.

    Requires publisher role. Creates a draft DPP with selected templates.
    """
    await require_access(tenant.user, "create", {"type": "dpp"}, tenant=tenant)
    service = DPPService(db)

    asset_ids_dict = body.asset_ids.model_dump(exclude_none=True)

    try:
        dpp = await service.create_dpp(
            tenant_id=tenant.tenant_id,
            tenant_slug=tenant.tenant_slug,
            owner_subject=tenant.user.sub,
            asset_ids=asset_ids_dict,
            selected_templates=body.selected_templates,
            initial_data=body.initial_data,
            required_specific_asset_ids=body.required_specific_asset_ids,
        )
    except IdentifierValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            "create_dpp_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            templates=body.selected_templates,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DPP creation failed due to an internal error",
        ) from exc

    await db.commit()
    await db.refresh(dpp)

    await record_epcis_lifecycle_event(
        session=db,
        dpp_id=dpp.id,
        tenant_id=tenant.tenant_id,
        action="create",
        created_by=tenant.user.sub,
    )
    await record_lifecycle_event(
        session=db,
        dpp_id=dpp.id,
        tenant_id=tenant.tenant_id,
        action="create",
        created_by=tenant.user.sub,
    )
    await db.commit()

    await emit_audit_event(
        db_session=db,
        action="create_dpp",
        resource_type="dpp",
        resource_id=dpp.id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
    )

    await trigger_webhooks(
        db,
        tenant.tenant_id,
        "DPP_CREATED",
        {
            "event": "DPP_CREATED",
            "dpp_id": str(dpp.id),
            "status": dpp.status.value,
            "owner_subject": dpp.owner_subject,
        },
    )

    owners = await load_users_by_subject(db, [dpp.owner_subject])
    return _dpp_response_payload(
        dpp,
        owner=actor_payload(dpp.owner_subject, owners),
        tenant=tenant,
        shared_with_current_user=False,
    )


@router.post("/batch-import", response_model=BatchImportResponse)
async def batch_import_dpps(
    body: BatchImportRequest,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> BatchImportResponse:
    """
    Batch create multiple DPPs.

    Each item is created in its own savepoint — one failure does not rollback others.
    Max 100 items per request.
    """
    await require_access(tenant.user, "create", {"type": "dpp"}, tenant=tenant)
    service = DPPService(db)
    results: list[BatchImportResultItem] = []
    payload_hash = hashlib.sha256(
        json.dumps(body.model_dump(mode="json"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    job = await service.create_batch_import_job(
        tenant_id=tenant.tenant_id,
        requested_by_subject=tenant.user.sub,
        payload_hash=payload_hash,
        total=len(body.dpps),
    )
    await emit_audit_event(
        db_session=db,
        action="batch_import_job_created",
        resource_type="batch_import_job",
        resource_id=str(job.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"total": len(body.dpps)},
    )

    for idx, item in enumerate(body.dpps):
        try:
            async with db.begin_nested():
                dpp = await service.create_dpp(
                    tenant_id=tenant.tenant_id,
                    tenant_slug=tenant.tenant_slug,
                    owner_subject=tenant.user.sub,
                    asset_ids=item.asset_ids.model_dump(exclude_none=True),
                    selected_templates=item.selected_templates,
                    initial_data=item.initial_data,
                    required_specific_asset_ids=item.required_specific_asset_ids,
                )
            result_item = BatchImportResultItem(index=idx, dpp_id=dpp.id, status="ok")
            results.append(result_item)
            await service.add_batch_import_item(
                tenant_id=tenant.tenant_id,
                job_id=job.id,
                item_index=idx,
                status="ok",
                dpp_id=dpp.id,
            )
            await emit_audit_event(
                db_session=db,
                action="batch_import_item",
                resource_type="batch_import_job",
                resource_id=str(job.id),
                tenant_id=tenant.tenant_id,
                user=tenant.user,
                request=request,
                metadata={"index": idx, "status": "ok", "dpp_id": str(dpp.id)},
            )
        except Exception:
            logger.warning("batch_import_item_failed", index=idx, exc_info=True)
            result_item = BatchImportResultItem(index=idx, status="failed", error="Import failed")
            results.append(result_item)
            await service.add_batch_import_item(
                tenant_id=tenant.tenant_id,
                job_id=job.id,
                item_index=idx,
                status="failed",
                error="Import failed",
            )
            await emit_audit_event(
                db_session=db,
                action="batch_import_item",
                resource_type="batch_import_job",
                resource_id=str(job.id),
                tenant_id=tenant.tenant_id,
                user=tenant.user,
                request=request,
                metadata={"index": idx, "status": "failed"},
            )

    succeeded = sum(1 for r in results if r.status == "ok")
    failed = len(results) - succeeded
    await service.finalize_batch_import_job(job=job, succeeded=succeeded, failed=failed)
    await db.commit()

    await emit_audit_event(
        db_session=db,
        action="batch_import",
        resource_type="batch_import_job",
        resource_id=str(job.id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={
            "total": len(body.dpps),
            "succeeded": succeeded,
            "failed": failed,
            "job_id": str(job.id),
        },
    )

    return BatchImportResponse(
        job_id=job.id,
        total=len(body.dpps),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )


@router.get("/batch-import/jobs", response_model=BatchImportJobListResponse)
async def list_batch_import_jobs(
    db: DbSession,
    tenant: TenantPublisher,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> BatchImportJobListResponse:
    """List persisted batch import jobs for this tenant."""
    service = DPPService(db)
    jobs, total_count = await service.list_batch_import_jobs(
        tenant_id=tenant.tenant_id,
        requester_subject=tenant.user.sub,
        is_tenant_admin=tenant.is_tenant_admin,
        limit=limit,
        offset=offset,
    )
    subjects = [job.requested_by_subject for job in jobs]
    users = await load_users_by_subject(db, subjects)
    payload = [
        BatchImportJobSummaryResponse(
            id=job.id,
            requested_by_subject=job.requested_by_subject,
            requested_by=ActorSummary(**actor_payload(job.requested_by_subject, users)),
            total=job.total,
            succeeded=job.succeeded,
            failed=job.failed,
            created_at=job.created_at.isoformat(),
        )
        for job in jobs
    ]
    return BatchImportJobListResponse(
        jobs=payload,
        count=len(payload),
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.get("/batch-import/jobs/{job_id}", response_model=BatchImportJobDetailResponse)
async def get_batch_import_job(
    job_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> BatchImportJobDetailResponse:
    """Get one persisted batch import job and its item outcomes."""
    service = DPPService(db)
    job = await service.get_batch_import_job(tenant_id=tenant.tenant_id, job_id=job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch import job {job_id} not found",
        )
    if not tenant.is_tenant_admin and job.requested_by_subject != tenant.user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    users = await load_users_by_subject(db, [job.requested_by_subject])
    return BatchImportJobDetailResponse(
        id=job.id,
        requested_by_subject=job.requested_by_subject,
        requested_by=ActorSummary(**actor_payload(job.requested_by_subject, users)),
        total=job.total,
        succeeded=job.succeeded,
        failed=job.failed,
        created_at=job.created_at.isoformat(),
        items=[
            BatchImportJobItemResponse(
                index=item.item_index,
                dpp_id=item.dpp_id,
                status=item.status,
                error=item.error,
                created_at=item.created_at.isoformat(),
            )
            for item in job.items
        ],
    )


@router.post("/import", response_model=DPPResponse, status_code=status.HTTP_201_CREATED)
async def import_dpp(
    body: ImportDPPRequest,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
    master_product_id: str | None = Query(
        None,
        description="Validate against a master template by product ID",
    ),
    master_version: str = Query("latest", description="Master version or alias"),
) -> DPPResponse:
    """
    Import a DPP from a JSON payload.

    Accepts a raw AAS environment JSON or an export payload with `aasEnvironment`.
    Optionally validates against a released master version.
    """
    await require_access(tenant.user, "create", {"type": "dpp"}, tenant=tenant)
    service = DPPService(db)

    payload = body.root
    aas_env = payload.get("aasEnvironment") if isinstance(payload, dict) else None
    if aas_env is None:
        aas_env = payload
    if not isinstance(aas_env, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AAS environment payload must be a JSON object",
        )

    validation = validate_aas_environment(aas_env)
    if validation.warnings:
        logger.warning(
            "import_dpp_validation_warnings",
            warning_count=len(validation.warnings),
        )
    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": validation.errors, "warnings": validation.warnings},
        )

    if master_product_id:
        master_service = DPPMasterService(db)
        result = await master_service.get_version_for_product(
            tenant.tenant_id,
            master_product_id,
            master_version,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Master template not found",
            )
        _, release = result
        aas_env, errors = master_service.validate_instance_payload(aas_env, release)
        if errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"errors": errors},
            )

    try:
        asset_ids = service.extract_asset_ids_from_environment(aas_env)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    existing = await service.find_existing_dpp(tenant.tenant_id, asset_ids)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "DPP already exists for the provided asset identifiers",
                "dpp_id": str(existing.id),
            },
        )

    try:
        dpp = await service.create_dpp_from_environment(
            tenant_id=tenant.tenant_id,
            tenant_slug=tenant.tenant_slug,
            owner_subject=tenant.user.sub,
            asset_ids=asset_ids,
            aas_env=aas_env,
        )
    except IdentifierValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    await db.commit()
    await db.refresh(dpp)

    await emit_audit_event(
        db_session=db,
        action="import_dpp",
        resource_type="dpp",
        resource_id=dpp.id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
    )

    owners = await load_users_by_subject(db, [dpp.owner_subject])
    return _dpp_response_payload(
        dpp,
        owner=actor_payload(dpp.owner_subject, owners),
        tenant=tenant,
        shared_with_current_user=False,
    )


@router.post("/import-aasx", response_model=DPPResponse, status_code=status.HTTP_201_CREATED)
async def import_dpp_aasx(
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
    file: UploadFile = File(...),
    master_product_id: str | None = Query(
        None,
        description="Validate against a master template by product ID",
    ),
    master_version: str = Query("latest", description="Master version or alias"),
) -> DPPResponse:
    """Import a DPP from an AASX package and persist supplementary files."""
    await require_access(tenant.user, "create", {"type": "dpp"}, tenant=tenant)
    if not file.filename or not file.filename.lower().endswith(".aasx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AASX import requires a .aasx file",
        )

    settings = get_settings()
    raw_bytes = await _read_upload_file_limited(file, max_bytes=settings.aasx_max_upload_bytes)
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded AASX file is empty",
        )

    ingest_service = AasxIngestService()
    try:
        ingest = ingest_service.parse(raw_bytes)
    except Exception as exc:
        logger.warning("import_dpp_aasx_parse_failed", filename=file.filename, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Failed to parse AASX package",
        ) from exc

    aas_env = ingest.aas_env_json
    validation = validate_aas_environment(aas_env)
    if validation.warnings:
        logger.warning(
            "import_dpp_aasx_validation_warnings",
            warning_count=len(validation.warnings),
        )
    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": validation.errors, "warnings": validation.warnings},
        )

    if master_product_id:
        master_service = DPPMasterService(db)
        result = await master_service.get_version_for_product(
            tenant.tenant_id,
            master_product_id,
            master_version,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Master template not found",
            )
        _, release = result
        aas_env, errors = master_service.validate_instance_payload(aas_env, release)
        if errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"errors": errors},
            )

    service = DPPService(db)
    try:
        asset_ids = service.extract_asset_ids_from_environment(aas_env)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    existing = await service.find_existing_dpp(tenant.tenant_id, asset_ids)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "DPP already exists for the provided asset identifiers",
                "dpp_id": str(existing.id),
            },
        )

    try:
        dpp = await service.create_dpp_from_environment(
            tenant_id=tenant.tenant_id,
            tenant_slug=tenant.tenant_slug,
            owner_subject=tenant.user.sub,
            asset_ids=asset_ids,
            aas_env=aas_env,
            doc_hints_manifest=ingest.doc_hints_manifest,
        )
    except IdentifierValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    supplementary_manifest: dict[str, Any] = {
        "files": [],
        "count": 0,
    }
    if ingest.supplementary_files:
        attachment_service = AttachmentService(db)
        for supplementary in ingest.supplementary_files:
            if supplementary.package_path.replace("\\", "/").endswith("/ui-hints.json"):
                continue
            filename = (
                supplementary.package_path.replace("\\", "/").split("/")[-1] or "attachment.bin"
            )
            uploaded = await attachment_service.upload_attachment_bytes(
                tenant_id=tenant.tenant_id,
                dpp_id=dpp.id,
                filename=filename,
                payload=supplementary.payload,
                created_by_subject=tenant.user.sub,
                requested_content_type=supplementary.content_type,
            )
            supplementary_manifest["files"].append(
                {
                    "package_path": supplementary.package_path,
                    "attachment_id": str(uploaded.attachment_id),
                    "content_type": uploaded.content_type,
                    "size_bytes": uploaded.size_bytes,
                    "sha256": supplementary.sha256,
                }
            )
        supplementary_manifest["count"] = len(supplementary_manifest["files"])

    latest_revision = await service.get_latest_revision(dpp.id, tenant.tenant_id)
    if latest_revision is not None:
        latest_revision.supplementary_manifest = supplementary_manifest
        if ingest.doc_hints_manifest is not None:
            latest_revision.doc_hints_manifest = ingest.doc_hints_manifest
        await db.flush()

    await db.commit()
    await db.refresh(dpp)

    await emit_audit_event(
        db_session=db,
        action="import_dpp_aasx",
        resource_type="dpp",
        resource_id=dpp.id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"supplementary_count": supplementary_manifest["count"]},
    )

    owners = await load_users_by_subject(db, [dpp.owner_subject])
    return _dpp_response_payload(
        dpp,
        owner=actor_payload(dpp.owner_subject, owners),
        tenant=tenant,
        shared_with_current_user=False,
    )


@router.post("/rebuild-all", response_model=BulkRebuildResponse)
async def rebuild_all_dpps(
    db: DbSession,
    tenant: TenantAdmin,
) -> BulkRebuildResponse:
    """
    Refresh templates and rebuild submodels for all DPPs.

    Requires tenant admin role.
    """
    template_service = TemplateRegistryService(db)
    await template_service.refresh_all_templates()

    service = DPPService(db)
    summary = await service.rebuild_all_from_templates(
        tenant_id=tenant.tenant_id,
        updated_by_subject=tenant.user.sub,
    )
    await db.commit()

    return BulkRebuildResponse(
        total=summary["total"],
        updated=summary["updated"],
        skipped=summary["skipped"],
        errors=[
            BulkRebuildError(dpp_id=entry["dpp_id"], error=entry["error"])
            for entry in summary.get("errors", [])
        ],
    )


@router.post("/repair-invalid-lists", response_model=RepairInvalidListsResponse)
async def repair_invalid_lists(
    body: RepairInvalidListsRequest,
    request: Request,
    db: DbSession,
    tenant: TenantAdmin,
) -> RepairInvalidListsResponse:
    """Repair latest revisions with invalid SubmodelElementList item idShorts."""
    service = DPPService(db)
    summary = await service.repair_invalid_list_item_id_shorts(
        tenant_id=tenant.tenant_id,
        updated_by_subject=tenant.user.sub,
        dry_run=body.dry_run,
        dpp_ids=body.dpp_ids,
        limit=body.limit,
    )
    await db.commit()
    await emit_audit_event(
        db_session=db,
        action="repair_invalid_lists",
        resource_type="dpp",
        resource_id=tenant.tenant_id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={
            "dry_run": body.dry_run,
            "target_count": len(body.dpp_ids or []),
            "repaired": summary["repaired"],
            "skipped": summary["skipped"],
        },
    )

    return RepairInvalidListsResponse(
        total=summary["total"],
        repaired=summary["repaired"],
        skipped=summary["skipped"],
        errors=[
            RepairInvalidListsError(
                dpp_id=entry["dpp_id"],
                reason=entry["reason"],
            )
            for entry in summary.get("errors", [])
        ],
        dry_run=summary["dry_run"],
        stats=RepairInvalidListsStats(**summary["stats"]),
    )


@router.get("", response_model=DPPListResponse)
async def list_dpps(
    db: DbSession,
    tenant: TenantContextDep,
    status_filter: DPPStatus | None = Query(None, alias="status"),
    scope: Literal["mine", "shared", "all"] = Query(
        "mine",
        description="Visibility filter: mine, shared, or all accessible resources",
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> DPPListResponse:
    """
    List DPPs accessible to the current user.
    """
    service = DPPService(db)
    dpps, total_count, shared_ids = await service.list_accessible_dpps(
        tenant_id=tenant.tenant_id,
        user_subject=tenant.user.sub,
        is_tenant_admin=tenant.is_tenant_admin,
        status=status_filter,
        scope=scope,
        limit=limit,
        offset=offset,
    )
    owners = await load_users_by_subject(db, [dpp.owner_subject for dpp in dpps])

    return DPPListResponse(
        dpps=[
            _dpp_response_payload(
                dpp,
                owner=actor_payload(dpp.owner_subject, owners),
                tenant=tenant,
                shared_with_current_user=dpp.id in shared_ids,
            )
            for dpp in dpps
        ],
        count=len(dpps),
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.get("/by-slug/{slug}", response_model=DPPDetailResponse)
async def get_dpp_by_slug(
    slug: str,
    db: DbSession,
    tenant: TenantContextDep,
) -> DPPDetailResponse:
    """
    Get a DPP by its short-link slug.

    The slug is the first 8 hex characters of the DPP UUID,
    as used in QR code short links (/p/{slug}).
    """
    service = DPPService(db)

    try:
        dpp = await service.get_dpp_by_slug(slug, tenant.tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP with slug {slug} not found",
        )

    shared_with_current_user = await service.is_resource_shared_with_user(
        tenant_id=tenant.tenant_id,
        resource_type="dpp",
        resource_id=dpp.id,
        user_subject=tenant.user.sub,
    )

    # Check access via ABAC
    await require_access(
        tenant.user,
        "read",
        build_dpp_resource_context(dpp, shared_with_current_user=shared_with_current_user),
        tenant=tenant,
    )

    revision = await _resolve_revision(
        service,
        dpp,
        tenant,
        shared_with_current_user=shared_with_current_user,
    )
    try:
        aas_environment = await service.get_revision_aas_for_reader(revision) if revision else None
    except Exception as exc:
        await emit_audit_event(
            db_session=db,
            action="decrypt_dpp_failed",
            resource_type="dpp",
            resource_id=dpp.id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            decision="deny",
            request=None,
            metadata={
                "revision_id": str(revision.id) if revision else None,
                "error": str(exc),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt encrypted DPP fields",
        ) from exc
    submodel_bindings = await service.get_submodel_bindings(revision=revision)
    constraints = await service.get_revision_publish_constraints(revision=revision)
    owners = await load_users_by_subject(db, [dpp.owner_subject])

    return DPPDetailResponse(
        **_dpp_response_payload(
            dpp,
            owner=actor_payload(dpp.owner_subject, owners),
            tenant=tenant,
            shared_with_current_user=shared_with_current_user,
        ).model_dump(),
        current_revision_no=revision.revision_no if revision else None,
        aas_environment=aas_environment,
        digest_sha256=revision.digest_sha256 if revision else None,
        required_specific_asset_ids=constraints["required_specific_asset_ids"],
        missing_required_specific_asset_ids=constraints["missing_required_specific_asset_ids"],
        publish_blockers=constraints["publish_blockers"],
        submodel_bindings=[
            SubmodelBindingResponse(
                submodel_id=binding.submodel_id,
                id_short=binding.id_short,
                semantic_id=binding.semantic_id,
                normalized_semantic_id=binding.normalized_semantic_id,
                template_key=binding.template_key,
                binding_source=binding.binding_source,
                idta_version=binding.idta_version,
                resolved_version=binding.resolved_version,
                support_status=binding.support_status,
                refresh_enabled=binding.refresh_enabled,
            )
            for binding in submodel_bindings
        ],
    )


@router.get("/{dpp_id}", response_model=DPPDetailResponse)
async def get_dpp(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantContextDep,
) -> DPPDetailResponse:
    """
    Get a specific DPP by ID.

    Returns full DPP details including current revision AAS environment.
    """
    service = DPPService(db)

    dpp = await service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    shared_with_current_user = await service.is_resource_shared_with_user(
        tenant_id=tenant.tenant_id,
        resource_type="dpp",
        resource_id=dpp.id,
        user_subject=tenant.user.sub,
    )

    # Check access via ABAC
    await require_access(
        tenant.user,
        "read",
        build_dpp_resource_context(dpp, shared_with_current_user=shared_with_current_user),
        tenant=tenant,
    )

    revision = await _resolve_revision(
        service,
        dpp,
        tenant,
        shared_with_current_user=shared_with_current_user,
    )
    try:
        aas_environment = await service.get_revision_aas_for_reader(revision) if revision else None
    except Exception as exc:
        await emit_audit_event(
            db_session=db,
            action="decrypt_dpp_failed",
            resource_type="dpp",
            resource_id=dpp.id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            decision="deny",
            request=None,
            metadata={
                "revision_id": str(revision.id) if revision else None,
                "error": str(exc),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt encrypted DPP fields",
        ) from exc
    submodel_bindings = await service.get_submodel_bindings(revision=revision)
    constraints = await service.get_revision_publish_constraints(revision=revision)
    owners = await load_users_by_subject(db, [dpp.owner_subject])

    return DPPDetailResponse(
        **_dpp_response_payload(
            dpp,
            owner=actor_payload(dpp.owner_subject, owners),
            tenant=tenant,
            shared_with_current_user=shared_with_current_user,
        ).model_dump(),
        current_revision_no=revision.revision_no if revision else None,
        aas_environment=aas_environment,
        digest_sha256=revision.digest_sha256 if revision else None,
        required_specific_asset_ids=constraints["required_specific_asset_ids"],
        missing_required_specific_asset_ids=constraints["missing_required_specific_asset_ids"],
        publish_blockers=constraints["publish_blockers"],
        submodel_bindings=[
            SubmodelBindingResponse(
                submodel_id=binding.submodel_id,
                id_short=binding.id_short,
                semantic_id=binding.semantic_id,
                normalized_semantic_id=binding.normalized_semantic_id,
                template_key=binding.template_key,
                binding_source=binding.binding_source,
                idta_version=binding.idta_version,
                resolved_version=binding.resolved_version,
                support_status=binding.support_status,
                refresh_enabled=binding.refresh_enabled,
            )
            for binding in submodel_bindings
        ],
    )


@router.put("/{dpp_id}/submodel", response_model=RevisionResponse)
async def update_submodel(
    dpp_id: UUID,
    body: UpdateSubmodelRequest,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> RevisionResponse:
    """
    Update a submodel within a DPP.

    Creates a new revision with the updated data.
    """
    service = DPPService(db)

    # Verify ownership
    dpp = await service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    if dpp.owner_subject != tenant.user.sub and not tenant.is_tenant_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can edit this DPP",
        )

    await require_access(
        tenant.user,
        "update",
        build_dpp_resource_context(dpp, shared_with_current_user=False),
        tenant=tenant,
    )

    try:
        revision = await service.update_submodel(
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            template_key=body.template_key,
            submodel_data=body.data,
            updated_by_subject=tenant.user.sub,
            rebuild_from_template=body.rebuild_from_template,
            submodel_id=body.submodel_id,
        )
        await db.commit()
        await emit_audit_event(
            db_session=db,
            action="update_submodel",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
            metadata={"template_key": body.template_key},
        )
    except AmbiguousSubmodelBindingError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(e),
                "template_key": e.template_key,
                "candidates": e.submodel_ids,
            },
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return RevisionResponse(
        id=revision.id,
        revision_no=revision.revision_no,
        state=revision.state.value,
        digest_sha256=revision.digest_sha256,
        created_by_subject=revision.created_by_subject,
        created_at=revision.created_at.isoformat(),
        template_provenance=revision.template_provenance,
    )


@router.put("/{dpp_id}/submodel-patch", response_model=RevisionResponse)
async def patch_submodel(
    dpp_id: UUID,
    body: PatchSubmodelRequest,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> RevisionResponse:
    """Update a submodel via deterministic canonical patch operations."""
    service = DPPService(db)
    dpp = await service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )
    if dpp.owner_subject != tenant.user.sub and not tenant.is_tenant_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can edit this DPP",
        )
    await require_access(
        tenant.user,
        "update",
        build_dpp_resource_context(dpp, shared_with_current_user=False),
        tenant=tenant,
    )

    try:
        revision = await service.patch_submodel(
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            template_key=body.template_key,
            operations=[operation.model_dump(exclude_none=True) for operation in body.operations],
            updated_by_subject=tenant.user.sub,
            submodel_id=body.submodel_id,
            strict=body.strict,
            base_revision_id=body.base_revision_id,
        )
        await db.commit()
        await emit_audit_event(
            db_session=db,
            action="patch_submodel",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
            metadata={
                "template_key": body.template_key,
                "operation_count": len(body.operations),
                "strict": body.strict,
            },
        )
    except AmbiguousSubmodelBindingError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(e),
                "template_key": e.template_key,
                "candidates": e.submodel_ids,
            },
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return RevisionResponse(
        id=revision.id,
        revision_no=revision.revision_no,
        state=revision.state.value,
        digest_sha256=revision.digest_sha256,
        created_by_subject=revision.created_by_subject,
        created_at=revision.created_at.isoformat(),
        template_provenance=revision.template_provenance,
    )


@router.post("/{dpp_id}/attachments", response_model=AttachmentUploadResponse)
async def upload_attachment(
    dpp_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
    file: UploadFile = File(...),
    content_type: str | None = Form(default=None),
) -> AttachmentUploadResponse:
    """Upload a tenant-private attachment linked to a DPP."""
    service = DPPService(db)
    dpp = await service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    if dpp.owner_subject != tenant.user.sub and not tenant.is_tenant_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can upload attachments for this DPP",
        )

    await require_access(
        tenant.user,
        "update",
        build_dpp_resource_context(dpp, shared_with_current_user=False),
        tenant=tenant,
    )

    attachment_service = AttachmentService(db)
    try:
        uploaded = await attachment_service.upload_attachment(
            tenant_id=tenant.tenant_id,
            dpp_id=dpp_id,
            upload_file=file,
            created_by_subject=tenant.user.sub,
            requested_content_type=content_type,
        )
        await db.commit()
        await emit_audit_event(
            db_session=db,
            action="upload_attachment",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
            metadata={
                "attachment_id": str(uploaded.attachment_id),
                "content_type": uploaded.content_type,
                "size_bytes": uploaded.size_bytes,
            },
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    private_url = (
        f"/api/v1/tenants/{tenant.tenant_slug}/dpps/{dpp_id}/attachments/{uploaded.attachment_id}"
    )
    return AttachmentUploadResponse(
        attachment_id=uploaded.attachment_id,
        content_type=uploaded.content_type,
        size_bytes=uploaded.size_bytes,
        url=private_url,
    )


@router.get("/{dpp_id}/attachments/{attachment_id}")
async def download_attachment(
    dpp_id: UUID,
    attachment_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantContextDep,
) -> StreamingResponse:
    """Download a tenant-private attachment (requires authenticated tenant access)."""
    service = DPPService(db)
    dpp = await service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    shared_with_current_user = await service.is_resource_shared_with_user(
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

    attachment_service = AttachmentService(db)
    try:
        attachment, payload = await attachment_service.download_attachment_bytes(
            tenant_id=tenant.tenant_id,
            dpp_id=dpp_id,
            attachment_id=attachment_id,
        )
    except AttachmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    await emit_audit_event(
        db_session=db,
        action="download_attachment",
        resource_type="dpp",
        resource_id=dpp_id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"attachment_id": str(attachment_id)},
    )
    headers = {
        "Content-Disposition": f'inline; filename="{attachment.filename}"',
        "Cache-Control": "private, no-store",
    }
    return StreamingResponse(
        io.BytesIO(payload),
        media_type=attachment.content_type,
        headers=headers,
    )


@router.post(
    "/{dpp_id}/submodels/refresh-rebuild",
    response_model=RefreshRebuildSubmodelsResponse,
)
async def refresh_rebuild_submodels(
    dpp_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> RefreshRebuildSubmodelsResponse:
    """Refresh templates and rebuild all bound submodels for one DPP."""
    service = DPPService(db)

    dpp = await service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    if dpp.owner_subject != tenant.user.sub and not tenant.is_tenant_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can edit this DPP",
        )

    await require_access(
        tenant.user,
        "update",
        build_dpp_resource_context(dpp, shared_with_current_user=False),
        tenant=tenant,
    )

    try:
        async with _acquire_refresh_rebuild_guard(db, dpp_id):
            summary = await service.refresh_and_rebuild_dpp_submodels(
                dpp_id=dpp_id,
                tenant_id=tenant.tenant_id,
                updated_by_subject=tenant.user.sub,
            )
            await db.commit()
            await emit_audit_event(
                db_session=db,
                action="refresh_rebuild_submodels",
                resource_type="dpp",
                resource_id=dpp_id,
                tenant_id=tenant.tenant_id,
                user=tenant.user,
                request=request,
                metadata={
                    "attempted": summary["attempted"],
                    "succeeded": len(summary["succeeded"]),
                    "failed": len(summary["failed"]),
                    "skipped": len(summary["skipped"]),
                },
            )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return RefreshRebuildSubmodelsResponse(
        attempted=summary["attempted"],
        succeeded=[RefreshRebuildSuccess(**entry) for entry in summary["succeeded"]],
        failed=[RefreshRebuildFailure(**entry) for entry in summary["failed"]],
        skipped=[RefreshRebuildSkipped(**entry) for entry in summary["skipped"]],
    )


@router.get(
    "/{dpp_id}/submodels/{template_key}/definition", response_model=SubmodelDefinitionResponse
)
async def get_submodel_definition(
    dpp_id: UUID,
    template_key: str,
    db: DbSession,
    tenant: TenantContextDep,
    revision: str | None = Query(None, description="latest or published"),
    revision_id: UUID | None = Query(None),
) -> SubmodelDefinitionResponse:
    """
    Get a submodel definition derived from a DPP revision environment.
    """
    service = DPPService(db)

    dpp = await service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    shared_with_current_user = await service.is_resource_shared_with_user(
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

    try:
        definition, used_revision = await service.get_submodel_definition(
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            template_key=template_key,
            revision_selector=revision,
            revision_id=revision_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return SubmodelDefinitionResponse(
        dpp_id=dpp_id,
        template_key=template_key,
        revision_id=used_revision.id,
        revision_no=used_revision.revision_no,
        state=used_revision.state.value,
        definition=definition,
    )


@router.post("/{dpp_id}/publish", response_model=DPPResponse)
async def publish_dpp(
    dpp_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> DPPResponse:
    """
    Publish a DPP, making it visible to viewers.
    """
    service = DPPService(db)

    # Verify ownership
    dpp = await service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    if dpp.owner_subject != tenant.user.sub and not tenant.is_tenant_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can publish this DPP",
        )

    await require_access(
        tenant.user,
        "publish",
        build_dpp_resource_context(dpp, shared_with_current_user=False),
        tenant=tenant,
    )

    try:
        published_dpp = await service.publish_dpp(
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            published_by_subject=tenant.user.sub,
        )
        await record_epcis_lifecycle_event(
            session=db,
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            action="publish",
            created_by=tenant.user.sub,
        )
        await record_lifecycle_event(
            session=db,
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            action="publish",
            created_by=tenant.user.sub,
        )
        await db.commit()
        await db.refresh(published_dpp)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    side_effect_timeout_seconds = max(get_settings().webhook_timeout_seconds, 1)

    async def _run_post_publish_side_effect(name: str, task: Any) -> None:
        try:
            await asyncio.wait_for(task, timeout=side_effect_timeout_seconds)
        except TimeoutError:
            logger.warning(
                "Post-publish side effect timed out",
                extra={
                    "side_effect": name,
                    "timeout_seconds": side_effect_timeout_seconds,
                    "dpp_id": str(dpp_id),
                    "tenant_id": str(tenant.tenant_id),
                },
            )
        except Exception:
            logger.warning(
                "Post-publish side effect failed",
                extra={
                    "side_effect": name,
                    "dpp_id": str(dpp_id),
                    "tenant_id": str(tenant.tenant_id),
                },
                exc_info=True,
            )

    # Post-commit side effects — failures are logged, not raised to the user
    await _run_post_publish_side_effect(
        "emit_audit_event",
        emit_audit_event(
            db_session=db,
            action="publish_dpp",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
        ),
    )

    await _run_post_publish_side_effect(
        "trigger_webhooks",
        trigger_webhooks(
            db,
            tenant.tenant_id,
            "DPP_PUBLISHED",
            {
                "event": "DPP_PUBLISHED",
                "dpp_id": str(dpp_id),
                "status": published_dpp.status.value,
            },
        ),
    )

    # Run resolver + registry auto-registration concurrently
    auto_tasks: list[tuple[str, Any]] = [
        (
            "auto_register_resolver_links",
            auto_register_resolver_links(db, published_dpp, tenant.tenant_id, tenant.user.sub),
        ),
    ]
    if published_dpp.current_published_revision_id:
        from sqlalchemy import select as _select

        from app.db.models import DPPRevision as _DPPRevision

        _rev_result = await db.execute(
            _select(_DPPRevision).where(
                _DPPRevision.id == published_dpp.current_published_revision_id
            )
        )
        _pub_rev = _rev_result.scalar_one_or_none()
        if _pub_rev:
            auto_tasks.append(
                (
                    "auto_register_shell_descriptor",
                    auto_register_shell_descriptor(
                        db, published_dpp, _pub_rev, tenant.tenant_id, tenant.user.sub
                    ),
                )
            )
    await asyncio.gather(
        *(
            _run_post_publish_side_effect(side_effect_name, side_effect_task)
            for side_effect_name, side_effect_task in auto_tasks
        )
    )

    owners = await load_users_by_subject(db, [published_dpp.owner_subject])
    return _dpp_response_payload(
        published_dpp,
        owner=actor_payload(published_dpp.owner_subject, owners),
        tenant=tenant,
        shared_with_current_user=False,
    )


@router.post("/{dpp_id}/archive", response_model=DPPResponse)
async def archive_dpp(
    dpp_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> DPPResponse:
    """
    Archive a DPP, marking it as no longer active.
    """
    service = DPPService(db)

    # Verify ownership
    dpp = await service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    if dpp.owner_subject != tenant.user.sub and not tenant.is_tenant_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can archive this DPP",
        )

    await require_access(
        tenant.user,
        "archive",
        build_dpp_resource_context(dpp, shared_with_current_user=False),
        tenant=tenant,
    )

    try:
        archived_dpp = await service.archive_dpp(dpp_id, tenant.tenant_id)
        await db.commit()
        await db.refresh(archived_dpp)
        await record_epcis_lifecycle_event(
            session=db,
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            action="archive",
            created_by=tenant.user.sub,
        )
        await record_lifecycle_event(
            session=db,
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            action="archive",
            created_by=tenant.user.sub,
        )
        await db.commit()
        await emit_audit_event(
            db_session=db,
            action="archive_dpp",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
        )

        await trigger_webhooks(
            db,
            tenant.tenant_id,
            "DPP_ARCHIVED",
            {
                "event": "DPP_ARCHIVED",
                "dpp_id": str(dpp_id),
                "status": archived_dpp.status.value,
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    owners = await load_users_by_subject(db, [archived_dpp.owner_subject])
    return _dpp_response_payload(
        archived_dpp,
        owner=actor_payload(archived_dpp.owner_subject, owners),
        tenant=tenant,
        shared_with_current_user=False,
    )


@router.get("/{dpp_id}/revisions", response_model=list[RevisionResponse])
async def list_revisions(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> list[RevisionResponse]:
    """
    List all revisions for a DPP.

    Requires publisher role and ownership.
    """
    service = DPPService(db)

    dpp = await service.get_dpp(dpp_id, tenant.tenant_id, include_revisions=True)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    if dpp.owner_subject != tenant.user.sub and not tenant.is_tenant_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return [
        RevisionResponse(
            id=rev.id,
            revision_no=rev.revision_no,
            state=rev.state.value,
            digest_sha256=rev.digest_sha256,
            created_by_subject=rev.created_by_subject,
            created_at=rev.created_at.isoformat(),
            template_provenance=rev.template_provenance,
        )
        for rev in dpp.revisions
    ]


@router.get("/{dpp_id}/diff", response_model=DPPDiffResult)
async def diff_revisions(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
    from_rev: int = Query(..., alias="from", description="Source revision number"),
    to_rev: int = Query(..., alias="to", description="Target revision number"),
) -> DPPDiffResult:
    """Compare two revisions of a DPP."""
    service = DPPService(db)

    dpp = await service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    if dpp.owner_subject != tenant.user.sub and not tenant.is_tenant_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    try:
        result = await service.diff_revisions(
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            rev_a=from_rev,
            rev_b=to_rev,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return DPPDiffResult(**result)


@router.get(
    "/{dpp_id}/digital-link",
    summary="Get GS1 Digital Link URI for a DPP",
)
async def get_dpp_digital_link(
    dpp_id: UUID,
    request: Request,
    db: DbSession,
    tenant: TenantContextDep,
) -> dict[str, str | bool | None]:
    """Return the canonical GS1 Digital Link URI for a DPP with GTIN."""
    service = DPPService(db)

    dpp = await service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )

    shared_with_current_user = await service.is_resource_shared_with_user(
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

    asset_ids = dpp.asset_ids or {}
    gtin = asset_ids.get("gtin")
    if not gtin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DPP has no GTIN in asset identifiers",
        )
    serial = asset_ids.get("serialNumber")
    settings = get_settings()
    resolver_base = settings.resolver_base_url or (
        f"https://{request.headers.get('host', 'localhost')}"
    )
    uri = _build_digital_link_uri(resolver_base, gtin, serial)
    return {
        "digital_link_uri": uri,
        "gtin": gtin,
        "serial_number": serial,
        "is_pseudo_gtin": gtin.startswith("0200"),
    }
