"""
API Router for DPP (Digital Product Passport) endpoints.
"""

import asyncio
import hashlib
import json
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, RootModel

from app.core.audit import emit_audit_event
from app.core.identifiers import IdentifierValidationError
from app.core.logging import get_logger
from app.core.security import require_access
from app.core.security.actor_metadata import actor_payload, load_users_by_subject
from app.core.security.resource_context import build_dpp_resource_context
from app.core.tenancy import TenantAdmin, TenantContext, TenantContextDep, TenantPublisher
from app.db.models import DPPStatus
from app.db.session import DbSession
from app.modules.digital_thread.handlers import record_lifecycle_event
from app.modules.dpps.service import DPPService
from app.modules.epcis.handlers import record_epcis_lifecycle_event
from app.modules.masters.service import DPPMasterService
from app.modules.registry.handlers import auto_register_shell_descriptor
from app.modules.resolver.handlers import auto_register_resolver_links
from app.modules.templates.service import TemplateRegistryService
from app.modules.webhooks.service import trigger_webhooks

logger = get_logger(__name__)
router = APIRouter()


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


class AssetIdsInput(BaseModel):
    """Input model for asset identifiers."""

    manufacturerPartId: str
    serialNumber: str | None = None
    batchId: str | None = None
    globalAssetId: str | None = None


class CreateDPPRequest(BaseModel):
    """Request model for creating a new DPP."""

    asset_ids: AssetIdsInput
    selected_templates: list[str] = Field(
        default=["digital-nameplate"],
        description="List of template keys to include",
    )
    initial_data: dict[str, Any] | None = None


class ImportDPPRequest(RootModel[dict[str, Any]]):
    """Request model for importing a DPP from JSON."""


class UpdateSubmodelRequest(BaseModel):
    """Request model for updating a submodel."""

    template_key: str
    data: dict[str, Any]
    rebuild_from_template: bool = False


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


class DPPDetailResponse(DPPResponse):
    """Detailed response model including revision data."""

    current_revision_no: int | None
    aas_environment: dict[str, Any] | None
    digest_sha256: str | None


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


class BatchImportItem(BaseModel):
    """Single item in a batch import request."""

    asset_ids: AssetIdsInput
    selected_templates: list[str] = Field(default=["digital-nameplate"])
    initial_data: dict[str, Any] | None = None


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
    owners = await load_users_by_subject(db, [dpp.owner_subject])

    return DPPDetailResponse(
        **_dpp_response_payload(
            dpp,
            owner=actor_payload(dpp.owner_subject, owners),
            tenant=tenant,
            shared_with_current_user=shared_with_current_user,
        ).model_dump(),
        current_revision_no=revision.revision_no if revision else None,
        aas_environment=revision.aas_env_json if revision else None,
        digest_sha256=revision.digest_sha256 if revision else None,
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
    owners = await load_users_by_subject(db, [dpp.owner_subject])

    return DPPDetailResponse(
        **_dpp_response_payload(
            dpp,
            owner=actor_payload(dpp.owner_subject, owners),
            tenant=tenant,
            shared_with_current_user=shared_with_current_user,
        ).model_dump(),
        current_revision_no=revision.revision_no if revision else None,
        aas_environment=revision.aas_env_json if revision else None,
        digest_sha256=revision.digest_sha256 if revision else None,
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
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return RevisionResponse(
        id=revision.id,
        revision_no=revision.revision_no,
        state=revision.state.value,
        digest_sha256=revision.digest_sha256,
        created_by_subject=revision.created_by_subject,
        created_at=revision.created_at.isoformat(),
        template_provenance=revision.template_provenance,
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
        await db.commit()
        await db.refresh(published_dpp)
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
        await emit_audit_event(
            db_session=db,
            action="publish_dpp",
            resource_type="dpp",
            resource_id=dpp_id,
            tenant_id=tenant.tenant_id,
            user=tenant.user,
            request=request,
        )

        await trigger_webhooks(
            db,
            tenant.tenant_id,
            "DPP_PUBLISHED",
            {
                "event": "DPP_PUBLISHED",
                "dpp_id": str(dpp_id),
                "status": published_dpp.status.value,
            },
        )
        # Run resolver + registry auto-registration concurrently
        auto_tasks: list[Any] = [
            auto_register_resolver_links(db, published_dpp, tenant.tenant_id, tenant.user.sub),
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
                    auto_register_shell_descriptor(
                        db, published_dpp, _pub_rev, tenant.tenant_id, tenant.user.sub
                    )
                )
        await asyncio.gather(*auto_tasks)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
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
