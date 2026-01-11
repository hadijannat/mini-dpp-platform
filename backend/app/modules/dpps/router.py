"""
API Router for DPP (Digital Product Passport) endpoints.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.identifiers import IdentifierValidationError
from app.core.security import require_access
from app.core.tenancy import TenantAdmin, TenantContextDep, TenantPublisher
from app.db.models import DPPStatus
from app.db.session import DbSession
from app.modules.dpps.service import DPPService
from app.modules.templates.service import TemplateRegistryService

router = APIRouter()


def _dpp_resource(dpp: Any) -> dict[str, Any]:
    """Build ABAC resource context for a DPP."""
    return {
        "type": "dpp",
        "id": str(dpp.id),
        "owner_subject": dpp.owner_subject,
        "status": dpp.status.value if hasattr(dpp.status, "value") else str(dpp.status),
    }


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


class UpdateSubmodelRequest(BaseModel):
    """Request model for updating a submodel."""

    template_key: str
    data: dict[str, Any]
    rebuild_from_template: bool = False


class DPPResponse(BaseModel):
    """Response model for DPP data."""

    id: UUID
    status: str
    owner_subject: str
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


@router.post("", response_model=DPPResponse, status_code=status.HTTP_201_CREATED)
async def create_dpp(
    request: CreateDPPRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> DPPResponse:
    """
    Create a new Digital Product Passport.

    Requires publisher role. Creates a draft DPP with selected templates.
    """
    await require_access(tenant.user, "create", {"type": "dpp"}, tenant=tenant)
    service = DPPService(db)

    asset_ids_dict = request.asset_ids.model_dump(exclude_none=True)

    try:
        dpp = await service.create_dpp(
            tenant_id=tenant.tenant_id,
            tenant_slug=tenant.tenant_slug,
            owner_subject=tenant.user.sub,
            asset_ids=asset_ids_dict,
            selected_templates=request.selected_templates,
            initial_data=request.initial_data,
        )
    except IdentifierValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    await db.commit()
    await db.refresh(dpp)

    return DPPResponse(
        id=dpp.id,
        status=dpp.status.value,
        owner_subject=dpp.owner_subject,
        asset_ids=dpp.asset_ids,
        qr_payload=dpp.qr_payload,
        created_at=dpp.created_at.isoformat(),
        updated_at=dpp.updated_at.isoformat(),
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
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> DPPListResponse:
    """
    List DPPs accessible to the current user.

    Publishers see their own DPPs. Viewers see all published DPPs.
    """
    service = DPPService(db)

    if tenant.is_tenant_admin:
        dpps = await service.get_dpps_for_tenant(
            tenant_id=tenant.tenant_id,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
    elif tenant.is_publisher:
        dpps = await service.get_dpps_for_owner(
            tenant_id=tenant.tenant_id,
            owner_subject=tenant.user.sub,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
    else:
        dpps = await service.get_published_dpps(
            tenant_id=tenant.tenant_id,
            limit=limit,
            offset=offset,
        )

    return DPPListResponse(
        dpps=[
            DPPResponse(
                id=dpp.id,
                status=dpp.status.value,
                owner_subject=dpp.owner_subject,
                asset_ids=dpp.asset_ids,
                qr_payload=dpp.qr_payload,
                created_at=dpp.created_at.isoformat(),
                updated_at=dpp.updated_at.isoformat(),
            )
            for dpp in dpps
        ],
        count=len(dpps),
        limit=limit,
        offset=offset,
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

    # Check access via ABAC
    await require_access(tenant.user, "read", _dpp_resource(dpp), tenant=tenant)

    # Get latest revision
    revision = await service.get_latest_revision(dpp_id, tenant.tenant_id)

    return DPPDetailResponse(
        id=dpp.id,
        status=dpp.status.value,
        owner_subject=dpp.owner_subject,
        asset_ids=dpp.asset_ids,
        qr_payload=dpp.qr_payload,
        created_at=dpp.created_at.isoformat(),
        updated_at=dpp.updated_at.isoformat(),
        current_revision_no=revision.revision_no if revision else None,
        aas_environment=revision.aas_env_json if revision else None,
        digest_sha256=revision.digest_sha256 if revision else None,
    )


@router.put("/{dpp_id}/submodel", response_model=RevisionResponse)
async def update_submodel(
    dpp_id: UUID,
    request: UpdateSubmodelRequest,
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

    await require_access(tenant.user, "update", _dpp_resource(dpp), tenant=tenant)

    try:
        revision = await service.update_submodel(
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            template_key=request.template_key,
            submodel_data=request.data,
            updated_by_subject=tenant.user.sub,
            rebuild_from_template=request.rebuild_from_template,
        )
        await db.commit()
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

    await require_access(tenant.user, "read", _dpp_resource(dpp), tenant=tenant)

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

    await require_access(tenant.user, "publish", _dpp_resource(dpp), tenant=tenant)

    try:
        published_dpp = await service.publish_dpp(
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            published_by_subject=tenant.user.sub,
        )
        await db.commit()
        await db.refresh(published_dpp)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return DPPResponse(
        id=published_dpp.id,
        status=published_dpp.status.value,
        owner_subject=published_dpp.owner_subject,
        asset_ids=published_dpp.asset_ids,
        qr_payload=published_dpp.qr_payload,
        created_at=published_dpp.created_at.isoformat(),
        updated_at=published_dpp.updated_at.isoformat(),
    )


@router.post("/{dpp_id}/archive", response_model=DPPResponse)
async def archive_dpp(
    dpp_id: UUID,
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

    await require_access(tenant.user, "archive", _dpp_resource(dpp), tenant=tenant)

    try:
        archived_dpp = await service.archive_dpp(dpp_id, tenant.tenant_id)
        await db.commit()
        await db.refresh(archived_dpp)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return DPPResponse(
        id=archived_dpp.id,
        status=archived_dpp.status.value,
        owner_subject=archived_dpp.owner_subject,
        asset_ids=archived_dpp.asset_ids,
        qr_payload=archived_dpp.qr_payload,
        created_at=archived_dpp.created_at.isoformat(),
        updated_at=archived_dpp.updated_at.isoformat(),
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
        )
        for rev in dpp.revisions
    ]
