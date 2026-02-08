"""Pydantic schemas for EPCIS 2.0 event capture and query.

All input schemas use camelCase field aliases matching the EPCIS 2.0
JSON/JSON-LD binding. Output schemas use ``from_attributes`` for
direct ORM mapping.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import EPCISEventType

# ---------------------------------------------------------------------------
# Shared sub-elements
# ---------------------------------------------------------------------------


class QuantityElement(BaseModel):
    """EPCIS quantity element for class-level identification."""

    model_config = ConfigDict(populate_by_name=True)

    epc_class: str = Field(alias="epcClass")
    quantity: float
    uom: str | None = None


class BizTransaction(BaseModel):
    """EPCIS business transaction reference."""

    model_config = ConfigDict(populate_by_name=True)

    type: str
    biz_transaction: str = Field(alias="bizTransaction")


class SensorMetadata(BaseModel):
    """Metadata for an EPCIS sensor element."""

    model_config = ConfigDict(populate_by_name=True)

    time: datetime | None = None
    device_id: str | None = Field(default=None, alias="deviceID")
    device_metadata: str | None = Field(default=None, alias="deviceMetadata")
    raw_data: str | None = Field(default=None, alias="rawData")


class SensorReport(BaseModel):
    """Individual sensor reading within a sensor element."""

    model_config = ConfigDict(populate_by_name=True)

    type: str | None = None
    value: float | None = None
    uom: str | None = None
    min_value: float | None = Field(default=None, alias="minValue")
    max_value: float | None = Field(default=None, alias="maxValue")
    mean_value: float | None = Field(default=None, alias="meanValue")


class SensorElement(BaseModel):
    """EPCIS sensor element containing metadata and report(s)."""

    model_config = ConfigDict(populate_by_name=True)

    sensor_metadata: SensorMetadata | None = Field(default=None, alias="sensorMetadata")
    sensor_report: list[SensorReport] = Field(default_factory=list, alias="sensorReport")


class ErrorDeclaration(BaseModel):
    """EPCIS error declaration for correcting a previous event."""

    model_config = ConfigDict(populate_by_name=True)

    declaration_time: datetime = Field(alias="declarationTime")
    reason: str | None = None
    corrective_event_ids: list[str] = Field(default_factory=list, alias="correctiveEventIDs")


# ---------------------------------------------------------------------------
# Event base + 5 concrete types
# ---------------------------------------------------------------------------


class EPCISEventBase(BaseModel):
    """Common fields shared by all EPCIS event types."""

    model_config = ConfigDict(populate_by_name=True)

    event_time: datetime = Field(alias="eventTime")
    event_time_zone_offset: str = Field(alias="eventTimeZoneOffset")
    record_time: datetime | None = Field(default=None, alias="recordTime")
    event_id: str | None = Field(default=None, alias="eventID")
    error_declaration: ErrorDeclaration | None = Field(default=None, alias="errorDeclaration")
    read_point: str | None = Field(default=None, alias="readPoint")
    biz_location: str | None = Field(default=None, alias="bizLocation")
    biz_step: str | None = Field(default=None, alias="bizStep")
    disposition: str | None = None
    sensor_element_list: list[SensorElement] = Field(
        default_factory=list, alias="sensorElementList"
    )


class ObjectEventCreate(EPCISEventBase):
    """EPCIS ObjectEvent — most common type, tracks observations of objects."""

    type: Literal["ObjectEvent"]
    epc_list: list[str] = Field(default_factory=list, alias="epcList")
    quantity_list: list[QuantityElement] = Field(default_factory=list, alias="quantityList")
    action: Literal["ADD", "OBSERVE", "DELETE"]
    biz_transaction_list: list[BizTransaction] = Field(
        default_factory=list, alias="bizTransactionList"
    )
    ilmd: dict[str, Any] | None = None


class AggregationEventCreate(EPCISEventBase):
    """EPCIS AggregationEvent — packing children into a parent container."""

    type: Literal["AggregationEvent"]
    parent_id: str | None = Field(default=None, alias="parentID")
    child_epcs: list[str] = Field(default_factory=list, alias="childEPCs")
    child_quantity_list: list[QuantityElement] = Field(
        default_factory=list, alias="childQuantityList"
    )
    action: Literal["ADD", "OBSERVE", "DELETE"]


class TransactionEventCreate(EPCISEventBase):
    """EPCIS TransactionEvent — associating objects with a business transaction."""

    type: Literal["TransactionEvent"]
    biz_transaction_list: list[BizTransaction] = Field(alias="bizTransactionList")
    epc_list: list[str] = Field(default_factory=list, alias="epcList")
    quantity_list: list[QuantityElement] = Field(default_factory=list, alias="quantityList")
    action: Literal["ADD", "OBSERVE", "DELETE"]
    parent_id: str | None = Field(default=None, alias="parentID")
    ilmd: dict[str, Any] | None = None


class TransformationEventCreate(EPCISEventBase):
    """EPCIS TransformationEvent — input objects transformed into outputs."""

    type: Literal["TransformationEvent"]
    input_epc_list: list[str] = Field(default_factory=list, alias="inputEPCList")
    input_quantity_list: list[QuantityElement] = Field(
        default_factory=list, alias="inputQuantityList"
    )
    output_epc_list: list[str] = Field(default_factory=list, alias="outputEPCList")
    output_quantity_list: list[QuantityElement] = Field(
        default_factory=list, alias="outputQuantityList"
    )
    transformation_id: str | None = Field(default=None, alias="transformationID")
    ilmd: dict[str, Any] | None = None


class AssociationEventCreate(EPCISEventBase):
    """EPCIS AssociationEvent — associating children with a parent (non-physical)."""

    type: Literal["AssociationEvent"]
    parent_id: str | None = Field(default=None, alias="parentID")
    child_epcs: list[str] = Field(default_factory=list, alias="childEPCs")
    child_quantity_list: list[QuantityElement] = Field(
        default_factory=list, alias="childQuantityList"
    )
    action: Literal["ADD", "OBSERVE", "DELETE"]


# Discriminated union over the ``type`` field
EPCISEventUnion = Annotated[
    ObjectEventCreate
    | AggregationEventCreate
    | TransactionEventCreate
    | TransformationEventCreate
    | AssociationEventCreate,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Document wrapper (capture input)
# ---------------------------------------------------------------------------


class EPCISBody(BaseModel):
    """Body of an EPCIS document containing the event list."""

    model_config = ConfigDict(populate_by_name=True)

    event_list: list[EPCISEventUnion] = Field(alias="eventList", max_length=10000)


class EPCISDocumentCreate(BaseModel):
    """EPCIS 2.0 Document — the top-level capture input.

    Mirrors the JSON-LD structure with ``@context``, ``type``,
    ``schemaVersion``, ``creationDate``, and ``epcisBody``.
    """

    model_config = ConfigDict(populate_by_name=True)

    context: list[str] = Field(alias="@context")
    type: Literal["EPCISDocument"] = "EPCISDocument"
    schema_version: str = Field(alias="schemaVersion")
    creation_date: datetime = Field(alias="creationDate")
    epcis_body: EPCISBody = Field(alias="epcisBody")


# ---------------------------------------------------------------------------
# Response / output schemas
# ---------------------------------------------------------------------------


class EPCISEventResponse(BaseModel):
    """Persisted EPCIS event returned from queries."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    dpp_id: UUID
    event_id: str
    event_type: str
    event_time: datetime
    event_time_zone_offset: str
    action: str | None = None
    biz_step: str | None = None
    disposition: str | None = None
    read_point: str | None = None
    biz_location: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    error_declaration: dict[str, Any] | None = None
    created_by_subject: str
    created_at: datetime


class EPCISQueryResponse(BaseModel):
    """EPCIS query result wrapper with JSON-LD context."""

    model_config = ConfigDict(populate_by_name=True)

    context: list[str] = Field(
        default=["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
        alias="@context",
    )
    type: str = "EPCISQueryDocument"
    event_list: list[EPCISEventResponse] = Field(alias="eventList")


# ---------------------------------------------------------------------------
# Public response schemas (exclude internal fields like created_by_subject)
# ---------------------------------------------------------------------------


class PublicEPCISEventResponse(BaseModel):
    """EPCIS event response for public (unauthenticated) endpoints.

    Excludes ``created_by_subject`` and ``created_at`` which are internal
    fields that should not be exposed to unauthenticated users.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    dpp_id: UUID
    event_id: str
    event_type: str
    event_time: datetime
    event_time_zone_offset: str
    action: str | None = None
    biz_step: str | None = None
    disposition: str | None = None
    read_point: str | None = None
    biz_location: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    error_declaration: dict[str, Any] | None = None


class PublicEPCISQueryResponse(BaseModel):
    """EPCIS query result wrapper for public (unauthenticated) endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    context: list[str] = Field(
        default=["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
        alias="@context",
    )
    type: str = "EPCISQueryDocument"
    event_list: list[PublicEPCISEventResponse] = Field(alias="eventList")


class CaptureResponse(BaseModel):
    """Response after successful event capture."""

    model_config = ConfigDict(populate_by_name=True)

    capture_id: str = Field(alias="captureId")
    event_count: int = Field(alias="eventCount")


class EPCISQueryParams(BaseModel):
    """Query parameters for EPCIS SimpleEventQuery."""

    event_type: EPCISEventType | None = None
    ge_event_time: datetime | None = None
    lt_event_time: datetime | None = None
    eq_action: str | None = None
    eq_biz_step: str | None = None
    eq_disposition: str | None = None
    match_epc: str | None = None
    match_any_epc: str | None = None
    match_parent_id: str | None = None
    match_input_epc: str | None = None
    match_output_epc: str | None = None
    eq_read_point: str | None = None
    eq_biz_location: str | None = None
    ge_record_time: datetime | None = None
    lt_record_time: datetime | None = None
    dpp_id: UUID | None = None
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Named query schemas
# ---------------------------------------------------------------------------


class NamedQueryCreate(BaseModel):
    """Input schema for creating a named EPCIS query."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    query_params: EPCISQueryParams


class NamedQueryResponse(BaseModel):
    """Persisted named query returned from API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    query_params: dict[str, Any]
    created_by_subject: str
    created_at: datetime
