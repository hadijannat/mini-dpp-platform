"""
Pydantic schemas for Data Carrier configuration and requests.
"""

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class CarrierFormat(str, Enum):
    """Supported data carrier formats."""

    QR_CODE = "qr"
    GS1_QR = "gs1_qr"
    DATA_MATRIX = "datamatrix"


class CarrierOutputType(str, Enum):
    """Supported output formats."""

    PNG = "png"
    SVG = "svg"
    PDF = "pdf"


class CarrierRequest(BaseModel):
    """Request model for generating a data carrier."""

    format: CarrierFormat = Field(
        default=CarrierFormat.QR_CODE,
        description="Type of data carrier to generate",
    )
    size: int = Field(
        default=400,
        ge=100,
        le=2000,
        description="Image size in pixels",
    )
    output_type: CarrierOutputType = Field(
        default=CarrierOutputType.PNG,
        description="Output file format",
    )
    background_color: str = Field(
        default="#FFFFFF",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Background color in hex format",
    )
    foreground_color: str = Field(
        default="#000000",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Foreground (code) color in hex format",
    )
    include_text: bool = Field(
        default=True,
        description="Whether to include product ID text below the code",
    )


class GS1DigitalLinkResponse(BaseModel):
    """Response model for GS1 Digital Link generation."""

    dpp_id: UUID
    digital_link: str = Field(description="GS1 Digital Link URL")
    gtin: str = Field(description="Global Trade Item Number")
    serial: str = Field(description="Serial number")
    resolver_url: str = Field(description="GS1 resolver base URL")
    is_pseudo_gtin: bool = Field(
        default=False,
        description="True if the GTIN was generated from the manufacturer part ID (not a real GS1 GTIN)",
    )


class IEC61406LinkResponse(BaseModel):
    """Response model for IEC 61406 identification link generation."""

    dpp_id: UUID
    identification_link: str = Field(description="IEC 61406 identification link URL")
    manufacturer_part_id: str = Field(default="", description="Manufacturer part ID")
    serial_number: str = Field(default="", description="Serial number")


class CarrierBatchRequest(BaseModel):
    """Request model for batch carrier generation."""

    dpp_ids: list[UUID] = Field(
        min_length=1,
        max_length=100,
        description="List of DPP IDs to generate carriers for",
    )
    settings: CarrierRequest = Field(
        default_factory=CarrierRequest,
        description="Carrier settings to apply to all",
    )


class CarrierResponse(BaseModel):
    """Response model for carrier generation metadata."""

    dpp_id: UUID
    format: CarrierFormat
    output_type: CarrierOutputType
    url: str = Field(description="URL encoded in the carrier")
    gs1_digital_link: str | None = Field(
        default=None,
        description="GS1 Digital Link if gs1_qr format",
    )
