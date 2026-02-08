"""Pydantic schemas for the AAS Registry & Discovery module."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shell Descriptor schemas
# ---------------------------------------------------------------------------


class ShellDescriptorCreate(BaseModel):
    """Input schema for creating a shell descriptor."""

    aas_id: str = Field(..., max_length=1024, description="AAS identifier")
    id_short: str = Field("", max_length=255, description="Short identifier")
    global_asset_id: str = Field("", max_length=1024, description="Global asset ID")
    specific_asset_ids: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Specific asset IDs (name/value pairs)",
    )
    submodel_descriptors: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Submodel descriptor objects",
    )
    dpp_id: UUID | None = Field(default=None, description="Associated DPP ID")


class ShellDescriptorUpdate(BaseModel):
    """Partial update schema for a shell descriptor."""

    id_short: str | None = None
    global_asset_id: str | None = None
    specific_asset_ids: list[dict[str, Any]] | None = None
    submodel_descriptors: list[dict[str, Any]] | None = None
    dpp_id: UUID | None = None


class SubmodelDescriptorResponse(BaseModel):
    """Submodel descriptor info extracted from a shell descriptor."""

    id: str
    id_short: str = ""
    semantic_id: str = ""
    endpoints: list[dict[str, Any]] = Field(default_factory=list)


class ShellDescriptorResponse(BaseModel):
    """Full shell descriptor response."""

    id: UUID
    tenant_id: UUID
    aas_id: str
    id_short: str
    global_asset_id: str
    specific_asset_ids: list[dict[str, Any]]
    submodel_descriptors: list[dict[str, Any]]
    dpp_id: UUID | None
    created_by_subject: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Asset Discovery schemas
# ---------------------------------------------------------------------------


class AssetDiscoveryCreate(BaseModel):
    """Input for creating a manual discovery mapping."""

    asset_id_key: str = Field(..., max_length=255)
    asset_id_value: str = Field(..., max_length=1024)
    aas_id: str = Field(..., max_length=1024)


class AssetDiscoveryResponse(BaseModel):
    """Discovery mapping response."""

    asset_id_key: str
    asset_id_value: str
    aas_id: str


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class RegistrySearchRequest(BaseModel):
    """Search request for finding shell descriptors by asset ID."""

    asset_id_key: str = Field(..., max_length=255)
    asset_id_value: str = Field(..., max_length=1024)
