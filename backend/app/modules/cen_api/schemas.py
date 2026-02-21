"""Schemas for the tenant/public CEN prEN 18222 API facade."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.identifiers.schemas import IdentifierEntityType, IdentifierGranularity


class CENCreateDPPRequest(BaseModel):
    """Create request for CEN facade DPP creation."""

    asset_ids: dict[str, Any] = Field(default_factory=dict)
    selected_templates: list[str] = Field(default_factory=lambda: ["digital-nameplate"])
    initial_data: dict[str, Any] | None = None
    required_specific_asset_ids: list[str] | None = None


class CENUpdateDPPRequest(BaseModel):
    """Partial update payload for CEN facade DPP updates."""

    asset_ids: dict[str, Any] | None = None
    visibility_scope: Literal["owner_team", "tenant"] | None = None


class CENDPPResponse(BaseModel):
    """Canonical CEN facade DPP payload."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    platform_id: UUID = Field(alias="platformId")
    status: str
    asset_ids: dict[str, Any]
    product_identifier: str | None = Field(default=None, alias="productIdentifier")
    identifier_scheme: str | None = Field(default=None, alias="identifierScheme")
    granularity: IdentifierGranularity | None = None
    created_at: datetime
    updated_at: datetime


class CENPaging(BaseModel):
    """Cursor-based paging metadata."""

    cursor: str | None = None


class CENDPPSearchResponse(BaseModel):
    """CEN DPP search response contract."""

    items: list[CENDPPResponse]
    paging: CENPaging


class CENValidateIdentifierRequest(BaseModel):
    """Identifier validation request."""

    entity_type: IdentifierEntityType
    scheme_code: str = Field(min_length=1, max_length=64)
    value_raw: str = Field(min_length=1)
    granularity: IdentifierGranularity | None = None


class CENValidateIdentifierResponse(BaseModel):
    """Identifier validation output with canonicalization."""

    valid: bool
    entity_type: IdentifierEntityType
    scheme_code: str
    value_raw: str
    value_canonical: str | None = None
    granularity: IdentifierGranularity | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CENRegisterIdentifierRequest(BaseModel):
    """Identifier register request."""

    entity_type: IdentifierEntityType
    scheme_code: str = Field(min_length=1, max_length=64)
    value_raw: str = Field(min_length=1)
    granularity: IdentifierGranularity | None = None
    dpp_id: UUID | None = None
    operator_id: UUID | None = None
    facility_id: UUID | None = None


class CENExternalIdentifierResponse(BaseModel):
    """Canonical identifier representation for CEN facade."""

    id: UUID
    tenant_id: UUID
    entity_type: IdentifierEntityType
    scheme_code: str
    value_raw: str
    value_canonical: str
    granularity: IdentifierGranularity | None = None
    status: str
    replaced_by_identifier_id: UUID | None = None
    issued_at: datetime | None = None
    deprecates_at: datetime | None = None
    created_by_subject: str
    created_at: datetime
    updated_at: datetime


class CENSupersedeIdentifierRequest(BaseModel):
    """Supersede request payload."""

    replacement_identifier_id: UUID


class CENSyncResponse(BaseModel):
    """Deterministic sync operation result payload."""

    dpp_id: UUID
    synced: bool
    target: Literal["registry", "resolver"]
    detail: str | None = None


class CENPublicDPPResponse(BaseModel):
    """Public CEN DPP payload (published-only, filtered)."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    status: str
    asset_ids: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    current_revision_no: int | None = None
    aas_environment: dict[str, Any] | None = None
    digest_sha256: str | None = None
    product_identifier: str | None = Field(default=None, alias="productIdentifier")
    identifier_scheme: str | None = Field(default=None, alias="identifierScheme")
    granularity: IdentifierGranularity | None = None
