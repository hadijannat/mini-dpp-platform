"""
API Router for Template Registry endpoints.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.security import CurrentUser, Publisher
from app.db.session import DbSession
from app.modules.templates.service import TemplateRegistryService

router = APIRouter()


class TemplateResponse(BaseModel):
    """Response model for template data."""

    id: UUID
    template_key: str
    idta_version: str
    semantic_id: str
    source_url: str
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


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    db: DbSession,
    _user: CurrentUser,
) -> TemplateListResponse:
    """
    List all registered templates.

    Returns all DPP4.0 templates that have been fetched and cached.
    """
    service = TemplateRegistryService(db)
    templates = await service.get_all_templates()

    return TemplateListResponse(
        templates=[
            TemplateResponse(
                id=t.id,
                template_key=t.template_key,
                idta_version=t.idta_version,
                semantic_id=t.semantic_id,
                source_url=t.source_url,
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
    _user: CurrentUser,
    version: str | None = None,
) -> TemplateResponse:
    """
    Get a specific template by key.

    Optionally specify a version, otherwise returns the pinned version.
    """
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
        semantic_id=template.semantic_id,
        source_url=template.source_url,
        fetched_at=template.fetched_at.isoformat(),
    )


@router.get("/{template_key}/schema", response_model=UISchemaResponse)
async def get_template_ui_schema(
    template_key: str,
    db: DbSession,
    _user: CurrentUser,
) -> UISchemaResponse:
    """
    Get the UI schema for a template.

    Returns a JSON Schema compatible structure for form rendering.
    """
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
    _user: Publisher,
) -> TemplateListResponse:
    """
    Refresh all templates from IDTA repository.

    Requires publisher role. Fetches and updates all DPP4.0 templates.
    """
    service = TemplateRegistryService(db)
    templates = await service.refresh_all_templates()

    return TemplateListResponse(
        templates=[
            TemplateResponse(
                id=t.id,
                template_key=t.template_key,
                idta_version=t.idta_version,
                semantic_id=t.semantic_id,
                source_url=t.source_url,
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
    _user: Publisher,
) -> TemplateResponse:
    """
    Refresh a specific template from IDTA repository.

    Requires publisher role.
    """
    service = TemplateRegistryService(db)

    try:
        template = await service.refresh_template(template_key)
        await db.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return TemplateResponse(
        id=template.id,
        template_key=template.template_key,
        idta_version=template.idta_version,
        semantic_id=template.semantic_id,
        source_url=template.source_url,
        fetched_at=template.fetched_at.isoformat(),
    )
