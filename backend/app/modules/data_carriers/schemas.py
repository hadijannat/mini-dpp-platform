"""Schemas for the data carrier lifecycle module."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class DataCarrierIdentityLevel(str, Enum):
    """Identity granularity for a data carrier."""

    MODEL = "model"
    BATCH = "batch"
    ITEM = "item"


class DataCarrierIdentifierScheme(str, Enum):
    """Identifier scheme encoded in the carrier."""

    GS1_GTIN = "gs1_gtin"
    GS1_EPC_TDS23 = "gs1_epc_tds23"
    IEC61406 = "iec61406"
    DIRECT_URL = "direct_url"


class DataCarrierType(str, Enum):
    """Carrier technology."""

    QR = "qr"
    DATAMATRIX = "datamatrix"
    NFC = "nfc"
    RFID = "rfid"


class DataCarrierResolverStrategy(str, Enum):
    """Resolver behavior for a carrier."""

    DYNAMIC_LINKSET = "dynamic_linkset"
    DIRECT_PUBLIC_DPP = "direct_public_dpp"


class DataCarrierStatus(str, Enum):
    """Carrier lifecycle state."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    WITHDRAWN = "withdrawn"


class RenderOutputType(str, Enum):
    """Renderable file types for carrier artifacts."""

    PNG = "png"
    SVG = "svg"
    PDF = "pdf"
    NDEF = "ndef"
    JSON = "json"
    CSV = "csv"


class RegistryExportFormat(str, Enum):
    """Supported registry export formats."""

    JSON = "json"
    CSV = "csv"


class DataCarrierIdentifierData(BaseModel):
    """Identifier components for creating a data carrier."""

    gtin: str | None = None
    serial: str | None = None
    batch: str | None = None
    manufacturer_part_id: str | None = None
    direct_url: HttpUrl | None = None
    tds_scheme: str | None = None
    epc_hex: str | None = None
    domain: str | None = None
    tag_length: int | None = None
    filter: int | None = None
    gs1_company_prefix_length: int | None = None


class DataCarrierLayoutProfile(BaseModel):
    """Rendering profile for the carrier visual asset."""

    size: int = Field(default=400, ge=100, le=2000)
    foreground_color: str = Field(default="#000000", pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    include_text: bool = True
    text_label: str | None = Field(default=None, max_length=120)
    error_correction: str = Field(default="H", pattern=r"^[LMQH]$")
    quiet_zone_modules: int = Field(default=4, ge=1, le=16)
    nfc_memory_bytes: int = Field(default=512, ge=16, le=8192)


class DataCarrierPlacementMetadata(BaseModel):
    """Placement and print metadata for a carrier."""

    target: str = Field(default="product", max_length=64)
    zone: str | None = Field(default=None, max_length=255)
    instructions: str | None = Field(default=None, max_length=1000)
    human_readable_fallback: str | None = Field(default=None, max_length=255)
    print_method: str | None = Field(default=None, max_length=64)
    substrate: str | None = Field(default=None, max_length=64)
    expected_lifetime_months: int | None = Field(default=None, ge=1, le=600)
    environment: str | None = Field(default=None, max_length=128)
    qa_grade: str | None = Field(default=None, max_length=32)


class DataCarrierCreateRequest(BaseModel):
    """Request payload to create a managed data carrier."""

    dpp_id: UUID
    identity_level: DataCarrierIdentityLevel = DataCarrierIdentityLevel.ITEM
    identifier_scheme: DataCarrierIdentifierScheme = DataCarrierIdentifierScheme.GS1_GTIN
    carrier_type: DataCarrierType = DataCarrierType.QR
    resolver_strategy: DataCarrierResolverStrategy = DataCarrierResolverStrategy.DYNAMIC_LINKSET
    identifier_data: DataCarrierIdentifierData = Field(default_factory=DataCarrierIdentifierData)
    layout_profile: DataCarrierLayoutProfile = Field(default_factory=DataCarrierLayoutProfile)
    placement_metadata: DataCarrierPlacementMetadata = Field(
        default_factory=DataCarrierPlacementMetadata
    )
    pre_sale_enabled: bool = True


class DataCarrierUpdateRequest(BaseModel):
    """Patch payload for mutable carrier fields only."""

    carrier_type: DataCarrierType | None = None
    resolver_strategy: DataCarrierResolverStrategy | None = None
    layout_profile: DataCarrierLayoutProfile | None = None
    placement_metadata: DataCarrierPlacementMetadata | None = None
    pre_sale_enabled: bool | None = None


class DataCarrierRenderRequest(BaseModel):
    """Render request for an existing carrier."""

    output_type: RenderOutputType = RenderOutputType.PNG
    persist_artifact: bool = False


class DataCarrierDeprecateRequest(BaseModel):
    """Deprecate a carrier, optionally linking a replacement."""

    replaced_by_carrier_id: UUID | None = None


class DataCarrierWithdrawRequest(BaseModel):
    """Withdraw a carrier from normal resolution."""

    reason: str = Field(min_length=3, max_length=1000)
    withdrawal_url: HttpUrl | None = None


class DataCarrierReissueRequest(BaseModel):
    """Reissue a carrier with same identity but fresh metadata."""

    carrier_type: DataCarrierType | None = None
    resolver_strategy: DataCarrierResolverStrategy | None = None
    layout_profile: DataCarrierLayoutProfile | None = None
    placement_metadata: DataCarrierPlacementMetadata | None = None
    pre_sale_enabled: bool | None = None


class DataCarrierResponse(BaseModel):
    """API response for a managed data carrier."""

    id: UUID
    tenant_id: UUID
    dpp_id: UUID
    identity_level: DataCarrierIdentityLevel
    identifier_scheme: DataCarrierIdentifierScheme
    carrier_type: DataCarrierType
    resolver_strategy: DataCarrierResolverStrategy
    status: DataCarrierStatus
    identifier_key: str
    identifier_data: dict[str, str]
    external_identifier_id: UUID | None
    encoded_uri: str
    payload_sha256: str | None
    layout_profile: dict[str, object]
    placement_metadata: dict[str, object]
    pre_sale_enabled: bool
    is_gtin_verified: bool
    replaced_by_carrier_id: UUID | None
    withdrawn_reason: str | None
    created_by_subject: str
    created_at: datetime
    updated_at: datetime


class DataCarrierArtifactResponse(BaseModel):
    """Response for a persisted carrier artifact reference."""

    id: UUID
    carrier_id: UUID
    artifact_type: str
    storage_uri: str
    sha256: str
    created_at: datetime


class DataCarrierPreSalePackResponse(BaseModel):
    """Pre-sale link package generated from a data carrier."""

    carrier_id: UUID
    dpp_id: UUID
    consumer_url: str
    encoded_uri: str
    widget_html: str


class DataCarrierRegistryExportItem(BaseModel):
    """Registry export line item."""

    carrier_id: UUID
    dpp_id: UUID
    identifier_key: str
    identifier_scheme: DataCarrierIdentifierScheme
    encoded_uri: str
    status: DataCarrierStatus
    created_at: datetime


class DataCarrierRegistryExportResponse(BaseModel):
    """JSON response for registry export."""

    items: list[DataCarrierRegistryExportItem]
    count: int


class DataCarrierListResponse(BaseModel):
    """Paginated list response for carriers."""

    items: list[DataCarrierResponse]
    count: int


class DataCarrierValidationRequest(BaseModel):
    """Pre-flight payload validation request."""

    carrier_type: DataCarrierType
    payload: str
    layout_profile: DataCarrierLayoutProfile = Field(default_factory=DataCarrierLayoutProfile)


class DataCarrierValidationResponse(BaseModel):
    """Pre-flight payload validation response."""

    valid: bool
    carrier_type: DataCarrierType
    payload_bytes: int
    warnings: list[str] = Field(default_factory=list)
    details: dict[str, object] = Field(default_factory=dict)


class DataCarrierQACheckResult(BaseModel):
    """Single QA check result."""

    check_type: str
    passed: bool
    severity: str = "info"
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class DataCarrierQAResponse(BaseModel):
    """Computed QA report for a carrier."""

    carrier_id: UUID
    checks: list[DataCarrierQACheckResult]


class DataCarrierQualityCheckCreateRequest(BaseModel):
    """Persisted quality-check input."""

    check_type: str = Field(min_length=3, max_length=64)
    passed: bool
    results: dict[str, object] = Field(default_factory=dict)


class DataCarrierQualityCheckResponse(BaseModel):
    """Persisted quality-check response."""

    id: UUID
    carrier_id: UUID
    check_type: str
    passed: bool
    results: dict[str, object]
    performed_by_subject: str
    performed_at: datetime
