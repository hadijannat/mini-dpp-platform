"""Schemas for RFID TDS encode/decode and read ingestion."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RFIDGS1Key(BaseModel):
    """Decoded GS1 key components."""

    gtin: str | None = None
    serial: str | None = None


class RFIDEncodeRequest(BaseModel):
    """Encode SGTIN++ payload to EPC hex."""

    tds_scheme: Literal["sgtin++"] = "sgtin++"
    hostname: str | None = None
    digital_link: str | None = None
    gtin: str | None = None
    serial: str | None = None
    tag_length: int = Field(default=96, ge=96, le=198)
    filter: int = Field(default=3, ge=0, le=7)
    gs1_company_prefix_length: int | None = Field(default=None, ge=6, le=12)


class RFIDEncodeResponse(BaseModel):
    """Encode response payload."""

    tds_scheme: str
    tag_length: int
    epc_hex: str
    tag_uri: str | None = None
    pure_identity_uri: str | None = None
    digital_link: str | None = None
    hostname: str | None = None
    gs1_key: RFIDGS1Key = Field(default_factory=RFIDGS1Key)
    fields: dict[str, str] = Field(default_factory=dict)


class RFIDDecodeRequest(BaseModel):
    """Decode EPC hex to GS1 key + Digital Link."""

    epc_hex: str = Field(..., min_length=4, max_length=512)
    tag_length: int = Field(default=96, ge=96, le=198)


class RFIDDecodeResponse(BaseModel):
    """Decode response payload."""

    tds_scheme: str
    tag_length: int
    epc_hex: str
    tag_uri: str | None = None
    pure_identity_uri: str | None = None
    digital_link: str | None = None
    hostname: str | None = None
    gs1_key: RFIDGS1Key = Field(default_factory=RFIDGS1Key)
    fields: dict[str, str] = Field(default_factory=dict)


class RFIDReadItem(BaseModel):
    """Single RFID read observation."""

    epc_hex: str = Field(..., min_length=4, max_length=512)
    observed_at: datetime | None = None
    tag_length: int = Field(default=96, ge=96, le=198)
    antenna: str | None = Field(default=None, max_length=128)
    rssi: float | None = None


class RFIDReadsIngestRequest(BaseModel):
    """RFID read ingestion payload."""

    reader_id: str = Field(..., min_length=1, max_length=128)
    read_point: str | None = Field(default=None, max_length=512)
    biz_location: str | None = Field(default=None, max_length=512)
    reads: list[RFIDReadItem] = Field(default_factory=list, min_length=1, max_length=5000)


class RFIDReadIngestResult(BaseModel):
    """Per-read ingestion outcome."""

    epc_hex: str
    matched: bool
    dpp_id: UUID | None = None
    event_id: str | None = None
    digital_link: str | None = None
    error: str | None = None


class RFIDReadsIngestResponse(BaseModel):
    """Aggregate read ingestion summary."""

    reader_id: str
    total_reads: int
    matched_reads: int
    created_events: int
    results: list[RFIDReadIngestResult] = Field(default_factory=list)
