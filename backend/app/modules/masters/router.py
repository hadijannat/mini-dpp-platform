"""API router for DPP master templates and versions."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.security import require_access
from app.core.tenancy import TenantContextDep, TenantPublisher
from app.db.session import DbSession
from app.modules.masters.service import DPPMasterService

router = APIRouter()


class MasterVariableInput(BaseModel):
    """Variable definition for DPP master templates."""

    name: str = Field(..., min_length=1)
    label: str | None = None
    description: str | None = None
    required: bool = True
    default_value: Any = None
    allow_default: bool = True
    expected_type: str = "string"
    constraints: dict[str, Any] | None = None


class MasterVariableResponse(MasterVariableInput):
    """Variable definition including resolved paths."""

    paths: list[dict[str, str]] = Field(default_factory=list)


class MasterCreateRequest(BaseModel):
    """Request model for creating a DPP master."""

    product_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str | None = None
    selected_templates: list[str] = Field(default_factory=list)
    asset_ids: dict[str, Any] | None = None
    initial_data: dict[str, Any] | None = None
    template_json: dict[str, Any] | None = None
    variables: list[MasterVariableInput] | None = None


class MasterUpdateRequest(BaseModel):
    """Request model for updating a DPP master."""

    name: str | None = None
    description: str | None = None
    selected_templates: list[str] | None = None
    asset_ids: dict[str, Any] | None = None
    initial_data: dict[str, Any] | None = None
    template_json: dict[str, Any] | None = None
    variables: list[MasterVariableInput] | None = None


class MasterVersionCreateRequest(BaseModel):
    """Request model for releasing a master version."""

    version: str = Field(..., min_length=1)
    aliases: list[str] = Field(default_factory=list)
    update_latest: bool = True


class MasterAliasesUpdateRequest(BaseModel):
    """Request model for updating version aliases."""

    aliases: list[str] = Field(default_factory=list)


class MasterResponse(BaseModel):
    """Response model for master metadata."""

    id: UUID
    product_id: str
    name: str
    description: str | None
    selected_templates: list[str]
    created_at: str
    updated_at: str


class MasterDetailResponse(MasterResponse):
    """Detailed master response including draft template."""

    draft_template_json: dict[str, Any]
    draft_variables: list[MasterVariableInput]


class MasterListResponse(BaseModel):
    """Response model for listing masters."""

    masters: list[MasterResponse]
    count: int


class MasterVersionResponse(BaseModel):
    """Response model for released master versions."""

    id: UUID
    version: str
    aliases: list[str]
    status: str
    released_at: str


class TemplatePackageResponse(BaseModel):
    """Template package response for SAP integration."""

    master_id: str
    product_id: str
    name: str
    version: str
    aliases: list[str]
    template_string: str
    variables: list[MasterVariableResponse]


@router.get("", response_model=MasterListResponse)
async def list_masters(
    db: DbSession,
    tenant: TenantContextDep,
    product_id: str | None = Query(None, description="Filter by product ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> MasterListResponse:
    await require_access(tenant.user, "read", {"type": "dpp_master"}, tenant=tenant)
    service = DPPMasterService(db)
    masters = await service.list_masters(
        tenant_id=tenant.tenant_id,
        product_id=product_id,
        limit=limit,
        offset=offset,
    )

    return MasterListResponse(
        masters=[
            MasterResponse(
                id=master.id,
                product_id=master.product_id,
                name=master.name,
                description=master.description,
                selected_templates=master.selected_templates,
                created_at=master.created_at.isoformat(),
                updated_at=master.updated_at.isoformat(),
            )
            for master in masters
        ],
        count=len(masters),
    )


@router.post("", response_model=MasterResponse, status_code=status.HTTP_201_CREATED)
async def create_master(
    request: MasterCreateRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> MasterResponse:
    await require_access(tenant.user, "create", {"type": "dpp_master"}, tenant=tenant)
    service = DPPMasterService(db)

    try:
        master = await service.create_master(
            tenant_id=tenant.tenant_id,
            created_by=tenant.user.sub,
            product_id=request.product_id,
            name=request.name,
            description=request.description,
            selected_templates=request.selected_templates,
            asset_ids=request.asset_ids,
            initial_data=request.initial_data,
            template_json=request.template_json,
            variables=[var.model_dump() for var in request.variables]
            if request.variables
            else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await db.commit()
    await db.refresh(master)

    return MasterResponse(
        id=master.id,
        product_id=master.product_id,
        name=master.name,
        description=master.description,
        selected_templates=master.selected_templates,
        created_at=master.created_at.isoformat(),
        updated_at=master.updated_at.isoformat(),
    )


@router.get("/{master_id}", response_model=MasterDetailResponse)
async def get_master(
    master_id: UUID,
    db: DbSession,
    tenant: TenantContextDep,
) -> MasterDetailResponse:
    await require_access(tenant.user, "read", {"type": "dpp_master"}, tenant=tenant)
    service = DPPMasterService(db)
    master = await service.get_master(master_id, tenant.tenant_id)
    if not master:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Master not found")

    return MasterDetailResponse(
        id=master.id,
        product_id=master.product_id,
        name=master.name,
        description=master.description,
        selected_templates=master.selected_templates,
        created_at=master.created_at.isoformat(),
        updated_at=master.updated_at.isoformat(),
        draft_template_json=master.draft_template_json,
        draft_variables=[MasterVariableInput(**entry) for entry in master.draft_variables],
    )


@router.get("/{master_id}/versions", response_model=list[MasterVersionResponse])
async def list_master_versions(
    master_id: UUID,
    db: DbSession,
    tenant: TenantContextDep,
) -> list[MasterVersionResponse]:
    await require_access(tenant.user, "read", {"type": "dpp_master"}, tenant=tenant)
    service = DPPMasterService(db)
    master = await service.get_master(master_id, tenant.tenant_id)
    if not master:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Master not found")

    versions = await service.list_versions(master.id)
    return [
        MasterVersionResponse(
            id=version.id,
            version=version.version,
            aliases=version.aliases,
            status=version.status.value,
            released_at=version.released_at.isoformat(),
        )
        for version in versions
    ]


@router.patch("/{master_id}", response_model=MasterDetailResponse)
async def update_master(
    master_id: UUID,
    request: MasterUpdateRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> MasterDetailResponse:
    await require_access(tenant.user, "update", {"type": "dpp_master"}, tenant=tenant)
    service = DPPMasterService(db)
    master = await service.get_master(master_id, tenant.tenant_id)
    if not master:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Master not found")

    try:
        updated = await service.update_master(
            master=master,
            updated_by=tenant.user.sub,
            name=request.name,
            description=request.description,
            selected_templates=request.selected_templates,
            asset_ids=request.asset_ids,
            initial_data=request.initial_data,
            template_json=request.template_json,
            variables=[var.model_dump() for var in request.variables]
            if request.variables
            else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await db.commit()
    await db.refresh(updated)

    return MasterDetailResponse(
        id=updated.id,
        product_id=updated.product_id,
        name=updated.name,
        description=updated.description,
        selected_templates=updated.selected_templates,
        created_at=updated.created_at.isoformat(),
        updated_at=updated.updated_at.isoformat(),
        draft_template_json=updated.draft_template_json,
        draft_variables=[MasterVariableInput(**entry) for entry in updated.draft_variables],
    )


@router.post(
    "/{master_id}/versions",
    response_model=MasterVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def release_master_version(
    master_id: UUID,
    request: MasterVersionCreateRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> MasterVersionResponse:
    await require_access(tenant.user, "release", {"type": "dpp_master"}, tenant=tenant)
    service = DPPMasterService(db)
    master = await service.get_master(master_id, tenant.tenant_id)
    if not master:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Master not found")

    try:
        version = await service.release_version(
            master=master,
            released_by=tenant.user.sub,
            version=request.version,
            aliases=request.aliases,
            update_latest=request.update_latest,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await db.commit()
    await db.refresh(version)

    return MasterVersionResponse(
        id=version.id,
        version=version.version,
        aliases=version.aliases,
        status=version.status.value,
        released_at=version.released_at.isoformat(),
    )


@router.patch("/{master_id}/versions/{version}/aliases", response_model=MasterVersionResponse)
async def update_master_aliases(
    master_id: UUID,
    version: str,
    request: MasterAliasesUpdateRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> MasterVersionResponse:
    await require_access(tenant.user, "update", {"type": "dpp_master"}, tenant=tenant)
    service = DPPMasterService(db)
    master = await service.get_master(master_id, tenant.tenant_id)
    if not master:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Master not found")

    resolved = await service.get_version_by_selector(master_id, version)
    if not resolved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    updated = await service.update_aliases(master, resolved, request.aliases)
    await db.commit()
    await db.refresh(updated)

    return MasterVersionResponse(
        id=updated.id,
        version=updated.version,
        aliases=updated.aliases,
        status=updated.status.value,
        released_at=updated.released_at.isoformat(),
    )


@router.get(
    "/by-product/{product_id}/versions/{version}/template",
    response_model=TemplatePackageResponse,
)
async def get_template_by_product(
    product_id: str,
    version: str,
    db: DbSession,
    tenant: TenantContextDep,
) -> TemplatePackageResponse:
    await require_access(tenant.user, "read", {"type": "dpp_master"}, tenant=tenant)
    service = DPPMasterService(db)
    result = await service.get_version_for_product(tenant.tenant_id, product_id, version)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    master, release = result
    package = service.build_template_package(master, release)

    return TemplatePackageResponse(
        master_id=package["master_id"],
        product_id=package["product_id"],
        name=package["name"],
        version=package["version"],
        aliases=package["aliases"],
        template_string=package["template_string"],
        variables=[MasterVariableResponse(**entry) for entry in package["variables"]],
    )


@router.get(
    "/by-product/{product_id}/versions/{version}/variables",
    response_model=list[MasterVariableResponse],
)
async def get_variables_by_product(
    product_id: str,
    version: str,
    db: DbSession,
    tenant: TenantContextDep,
) -> list[MasterVariableResponse]:
    await require_access(tenant.user, "read", {"type": "dpp_master"}, tenant=tenant)
    service = DPPMasterService(db)
    result = await service.get_version_for_product(tenant.tenant_id, product_id, version)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    _, release = result
    return [MasterVariableResponse(**entry) for entry in release.variables]
