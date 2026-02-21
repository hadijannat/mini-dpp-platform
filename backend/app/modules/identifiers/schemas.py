"""Schemas for CEN identifier governance APIs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class IdentifierEntityType(str, Enum):
    PRODUCT = "product"
    OPERATOR = "operator"
    FACILITY = "facility"


class IdentifierGranularity(str, Enum):
    MODEL = "model"
    BATCH = "batch"
    ITEM = "item"


class IdentifierValidateRequest(BaseModel):
    entity_type: IdentifierEntityType
    scheme_code: str = Field(min_length=1, max_length=64)
    value_raw: str = Field(min_length=1)
    granularity: IdentifierGranularity | None = None


class IdentifierValidateResponse(BaseModel):
    valid: bool
    entity_type: IdentifierEntityType
    scheme_code: str
    value_raw: str
    value_canonical: str | None = None
    granularity: IdentifierGranularity | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class IdentifierRegisterRequest(BaseModel):
    entity_type: IdentifierEntityType
    scheme_code: str = Field(min_length=1, max_length=64)
    value_raw: str = Field(min_length=1)
    granularity: IdentifierGranularity | None = None
    dpp_id: UUID | None = None
    operator_id: UUID | None = None
    facility_id: UUID | None = None


class IdentifierSupersedeRequest(BaseModel):
    replacement_identifier_id: UUID


class ExternalIdentifierResponse(BaseModel):
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


class EconomicOperatorCreateRequest(BaseModel):
    legal_name: str = Field(min_length=1, max_length=255)
    country: str | None = Field(default=None, max_length=8)
    metadata_json: dict[str, object] = Field(default_factory=dict)
    identifier: IdentifierRegisterRequest | None = None


class EconomicOperatorResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    legal_name: str
    country: str | None = None
    metadata_json: dict[str, object]
    created_by_subject: str
    created_at: datetime
    updated_at: datetime


class FacilityCreateRequest(BaseModel):
    operator_id: UUID
    facility_name: str = Field(min_length=1, max_length=255)
    address: dict[str, object] = Field(default_factory=dict)
    metadata_json: dict[str, object] = Field(default_factory=dict)
    identifier: IdentifierRegisterRequest | None = None


class FacilityResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    operator_id: UUID
    facility_name: str
    address: dict[str, object]
    metadata_json: dict[str, object]
    created_by_subject: str
    created_at: datetime
    updated_at: datetime
