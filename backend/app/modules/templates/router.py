"""
API Router for Template Registry endpoints.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.security import CurrentUser, Publisher, require_access
from app.db.session import DbSession
from app.modules.templates.service import (
    TemplateFetchError,
    TemplateParseError,
    TemplateRegistryService,
)

router = APIRouter()


class TemplateResponse(BaseModel):
    """Response model for template data."""

    id: UUID
    template_key: str
    idta_version: str
    resolved_version: str | None = None
    semantic_id: str
    source_url: str
    source_repo_ref: str | None = None
    source_file_path: str | None = None
    source_file_sha: str | None = None
    source_kind: str | None = None
    selection_strategy: str | None = None
    fetched_at: str

    model_config = ConfigDict(from_attributes=True)


class TemplateListResponse(BaseModel):
    """Response model for list of templates."""

    templates: list[TemplateResponse]
    count: int


class UISchemaResponse(BaseModel):
    """Response model for UI schema."""

    template_key: str
    schema_: dict[str, Any] = Field(alias="schema")

    model_config = ConfigDict(populate_by_name=True)


class TemplateDefinitionResponse(BaseModel):
    """Response model for template definition AST."""

    template_key: str
    definition: dict[str, Any]


class TemplateSourceMetadataResponse(BaseModel):
    """Response model for resolved upstream template source metadata."""

    resolved_version: str
    source_repo_ref: str
    source_file_path: str | None = None
    source_file_sha: str | None = None
    source_kind: str | None = None
    selection_strategy: str | None = None
    source_url: str


class TemplateContractResponse(BaseModel):
    """Response model for canonical template contract used by frontend form generation."""

    template_key: str
    idta_version: str
    semantic_id: str
    definition: dict[str, Any]
    schema_: dict[str, Any] = Field(alias="schema")
    source_metadata: TemplateSourceMetadataResponse

    model_config = ConfigDict(populate_by_name=True)


@router.get("/{template_key}/definition", response_model=TemplateDefinitionResponse)
async def get_template_definition(
    template_key: str,
    db: DbSession,
    user: CurrentUser,
) -> TemplateDefinitionResponse:
    """
    Get the template definition AST (BaSyx parsed).

    Returns a stable representation of the submodel template tree.
    """
    await require_access(user, "read", {"type": "template"})
    service = TemplateRegistryService(db)
    template = await service.get_template(template_key)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_key}' not found",
        )

    try:
        definition = service.generate_template_definition(template)
    except TemplateParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )

    return TemplateDefinitionResponse(
        template_key=template_key,
        definition=definition,
    )


@router.get("/{template_key}/contract", response_model=TemplateContractResponse)
async def get_template_contract(
    template_key: str,
    db: DbSession,
    user: CurrentUser,
) -> TemplateContractResponse:
    """
    Get canonical template contract (definition + schema + source metadata).
    """
    await require_access(user, "read", {"type": "template"})
    service = TemplateRegistryService(db)
    template = await service.get_template(template_key)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_key}' not found",
        )

    contract = service.generate_template_contract(template)
    return TemplateContractResponse(
        template_key=template_key,
        idta_version=contract["idta_version"],
        semantic_id=contract["semantic_id"],
        definition=contract["definition"],
        schema_=contract["schema"],
        source_metadata=TemplateSourceMetadataResponse(**contract["source_metadata"]),
    )


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    db: DbSession,
    user: CurrentUser,
) -> TemplateListResponse:
    """
    List all registered templates.

    Returns all DPP4.0 templates that have been fetched and cached.
    """
    await require_access(user, "read", {"type": "template"})
    service = TemplateRegistryService(db)
    templates = await service.get_all_templates()

    return TemplateListResponse(
        templates=[
            TemplateResponse(
                id=t.id,
                template_key=t.template_key,
                idta_version=t.idta_version,
                resolved_version=t.resolved_version,
                semantic_id=t.semantic_id,
                source_url=t.source_url,
                source_repo_ref=t.source_repo_ref,
                source_file_path=t.source_file_path,
                source_file_sha=t.source_file_sha,
                source_kind=t.source_kind,
                selection_strategy=t.selection_strategy,
                fetched_at=t.fetched_at.isoformat(),
            )
            for t in templates
        ],
        count=len(templates),
    )


@router.get("/{template_key}", response_model=TemplateResponse)
async def get_template(
    template_key: str,
    db: DbSession,
    user: CurrentUser,
    version: str | None = None,
) -> TemplateResponse:
    """
    Get a specific template by key.

    Optionally specify a version, otherwise returns the pinned version.
    """
    await require_access(user, "read", {"type": "template"})
    service = TemplateRegistryService(db)
    template = await service.get_template(template_key, version)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_key}' not found",
        )

    return TemplateResponse(
        id=template.id,
        template_key=template.template_key,
        idta_version=template.idta_version,
        resolved_version=template.resolved_version,
        semantic_id=template.semantic_id,
        source_url=template.source_url,
        source_repo_ref=template.source_repo_ref,
        source_file_path=template.source_file_path,
        source_file_sha=template.source_file_sha,
        source_kind=template.source_kind,
        selection_strategy=template.selection_strategy,
        fetched_at=template.fetched_at.isoformat(),
    )


@router.get("/{template_key}/schema", response_model=UISchemaResponse)
async def get_template_ui_schema(
    template_key: str,
    db: DbSession,
    user: CurrentUser,
) -> UISchemaResponse:
    """
    Get the UI schema for a template.

    Returns a JSON Schema compatible structure for form rendering.
    """
    await require_access(user, "read", {"type": "template"})
    service = TemplateRegistryService(db)
    template = await service.get_template(template_key)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_key}' not found",
        )

    schema = service.generate_ui_schema(template)

    return UISchemaResponse(
        template_key=template_key,
        schema_=schema,
    )


@router.post("/refresh", response_model=TemplateListResponse)
async def refresh_templates(
    db: DbSession,
    user: Publisher,
) -> TemplateListResponse:
    """
    Refresh all templates from IDTA repository.

    Requires publisher role. Fetches and updates all DPP4.0 templates.
    """
    await require_access(user, "refresh", {"type": "template"})
    service = TemplateRegistryService(db)
    templates = await service.refresh_all_templates()

    return TemplateListResponse(
        templates=[
            TemplateResponse(
                id=t.id,
                template_key=t.template_key,
                idta_version=t.idta_version,
                resolved_version=t.resolved_version,
                semantic_id=t.semantic_id,
                source_url=t.source_url,
                source_repo_ref=t.source_repo_ref,
                source_file_path=t.source_file_path,
                source_file_sha=t.source_file_sha,
                source_kind=t.source_kind,
                selection_strategy=t.selection_strategy,
                fetched_at=t.fetched_at.isoformat(),
            )
            for t in templates
        ],
        count=len(templates),
    )


@router.post("/refresh/{template_key}", response_model=TemplateResponse)
async def refresh_template(
    template_key: str,
    db: DbSession,
    user: Publisher,
) -> TemplateResponse:
    """
    Refresh a specific template from IDTA repository.

    Requires publisher role.
    """
    await require_access(user, "refresh", {"type": "template"})
    service = TemplateRegistryService(db)

    try:
        template = await service.refresh_template(template_key)
        await db.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except TemplateFetchError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )

    return TemplateResponse(
        id=template.id,
        template_key=template.template_key,
        idta_version=template.idta_version,
        resolved_version=template.resolved_version,
        semantic_id=template.semantic_id,
        source_url=template.source_url,
        source_repo_ref=template.source_repo_ref,
        source_file_path=template.source_file_path,
        source_file_sha=template.source_file_sha,
        source_kind=template.source_kind,
        selection_strategy=template.selection_strategy,
        fetched_at=template.fetched_at.isoformat(),
    )
