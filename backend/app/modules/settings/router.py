"""
Admin settings endpoints.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.identifiers import IdentifierValidationError, normalize_base_uri
from app.core.security import Admin, require_access
from app.core.settings_service import SettingsService
from app.db.session import DbSession

router = APIRouter()


class GlobalAssetIdBaseUriResponse(BaseModel):
    """Response model for global asset ID base URI."""

    global_asset_id_base_uri: str


class GlobalAssetIdBaseUriUpdateRequest(BaseModel):
    """Request model for updating global asset ID base URI."""

    global_asset_id_base_uri: str = Field(..., min_length=1)


@router.get("/global-asset-id-base-uri", response_model=GlobalAssetIdBaseUriResponse)
async def get_global_asset_id_base_uri(
    db: DbSession,
    user: Admin,
) -> GlobalAssetIdBaseUriResponse:
    """
    Get the current global asset ID base URI.

    Requires admin role.
    """
    await require_access(
        user,
        "read",
        {"type": "setting", "key": "global_asset_id_base_uri"},
    )
    service = SettingsService(db)
    stored = await service.get_setting("global_asset_id_base_uri")
    base_uri = stored or get_settings().global_asset_id_base_uri_default
    try:
        normalized = normalize_base_uri(base_uri)
    except IdentifierValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return GlobalAssetIdBaseUriResponse(global_asset_id_base_uri=normalized)


@router.put("/global-asset-id-base-uri", response_model=GlobalAssetIdBaseUriResponse)
async def update_global_asset_id_base_uri(
    request: GlobalAssetIdBaseUriUpdateRequest,
    db: DbSession,
    user: Admin,
) -> GlobalAssetIdBaseUriResponse:
    """
    Update the global asset ID base URI.

    Requires admin role.
    """
    await require_access(
        user,
        "update",
        {"type": "setting", "key": "global_asset_id_base_uri"},
    )
    try:
        normalized = normalize_base_uri(request.global_asset_id_base_uri)
    except IdentifierValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    service = SettingsService(db)
    await service.set_setting(
        "global_asset_id_base_uri",
        normalized,
        updated_by=user.sub,
    )

    return GlobalAssetIdBaseUriResponse(global_asset_id_base_uri=normalized)
