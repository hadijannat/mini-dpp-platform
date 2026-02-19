"""Pydantic schemas for OPC UA source, nodeset, and mapping endpoints.

Input schemas use camelCase aliases. Output schemas use ``from_attributes``
for direct ORM mapping.
"""

from __future__ import annotations

from datetime import date, datetime
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models import (
    DPPBindingMode,
    OPCUAAuthType,
    OPCUAConnectionStatus,
    OPCUAMappingType,
)


def _validate_opcua_endpoint_url(url: str) -> str:
    """Validate OPC UA endpoint URL: must be opc.tcp:// and not target private IPs.

    Prevents SSRF by blocking loopback, link-local, and RFC 1918 private addresses.
    """
    parsed = urlparse(url)
    if parsed.scheme != "opc.tcp":
        raise ValueError("Endpoint URL must use the opc.tcp:// scheme")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Endpoint URL must include a hostname")
    # Block known dangerous hostnames
    _blocked = {"localhost", "metadata.google.internal", "169.254.169.254"}
    if hostname.lower() in _blocked:
        raise ValueError(f"Endpoint URL hostname '{hostname}' is not allowed")
    # Try to parse as IP and block private/loopback/link-local ranges
    try:
        addr = ip_address(hostname)
        if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_reserved:
            raise ValueError(
                f"Endpoint URL must not target private/loopback/link-local address: {hostname}"
            )
    except ValueError as exc:
        # Re-raise our own validation errors; ignore parse failures (hostname is a DNS name)
        if "must not target" in str(exc) or "not allowed" in str(exc):
            raise
    return url


# ---------------------------------------------------------------------------
# OPC UA Source
# ---------------------------------------------------------------------------


class OPCUASourceCreate(BaseModel):
    """Create a new OPC UA source."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=255)
    endpoint_url: str = Field(
        min_length=1,
        alias="endpointUrl",
        description="OPC UA endpoint URL, e.g. opc.tcp://host:4840",
    )
    security_policy: str | None = Field(default=None, alias="securityPolicy")
    security_mode: str | None = Field(default=None, alias="securityMode")
    auth_type: OPCUAAuthType = Field(default=OPCUAAuthType.ANONYMOUS, alias="authType")
    username: str | None = None
    password: str | None = Field(
        default=None,
        description="Plaintext password — encrypted before storage",
        exclude=True,  # Never serialized back
    )
    client_cert_ref: str | None = Field(default=None, alias="clientCertRef")
    client_key_ref: str | None = Field(default=None, alias="clientKeyRef")
    server_cert_pinned_sha256: str | None = Field(
        default=None,
        alias="serverCertPinnedSha256",
        max_length=64,
    )

    @field_validator("endpoint_url")
    @classmethod
    def validate_endpoint_url(cls, v: str) -> str:
        return _validate_opcua_endpoint_url(v)


class OPCUASourceUpdate(BaseModel):
    """Partial update for an OPC UA source."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    endpoint_url: str | None = Field(default=None, alias="endpointUrl")
    security_policy: str | None = Field(default=None, alias="securityPolicy")
    security_mode: str | None = Field(default=None, alias="securityMode")
    auth_type: OPCUAAuthType | None = Field(default=None, alias="authType")
    username: str | None = None
    password: str | None = Field(default=None, exclude=True)
    client_cert_ref: str | None = Field(default=None, alias="clientCertRef")
    client_key_ref: str | None = Field(default=None, alias="clientKeyRef")
    server_cert_pinned_sha256: str | None = Field(default=None, alias="serverCertPinnedSha256")

    @field_validator("endpoint_url")
    @classmethod
    def validate_endpoint_url(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_opcua_endpoint_url(v)
        return v


class OPCUASourceResponse(BaseModel):
    """OPC UA source detail — password is NEVER exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    endpoint_url: str
    security_policy: str | None = None
    security_mode: str | None = None
    auth_type: OPCUAAuthType
    username: str | None = None
    has_password: bool = False
    client_cert_ref: str | None = None
    client_key_ref: str | None = None
    server_cert_pinned_sha256: str | None = None
    connection_status: OPCUAConnectionStatus
    last_seen_at: datetime | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class OPCUASourceListResponse(BaseModel):
    """Paginated list of OPC UA sources."""

    items: list[OPCUASourceResponse]
    total: int


class TestConnectionResult(BaseModel):
    """Result of an OPC UA test-connection probe."""

    success: bool
    server_info: dict[str, Any] | None = Field(default=None, alias="serverInfo")
    error: str | None = None
    latency_ms: float | None = Field(default=None, alias="latencyMs")


# ---------------------------------------------------------------------------
# OPC UA NodeSet
# ---------------------------------------------------------------------------


class OPCUANodeSetUploadMeta(BaseModel):
    """Metadata sent alongside a NodeSet upload (form fields or JSON)."""

    model_config = ConfigDict(populate_by_name=True)

    source_id: UUID | None = Field(default=None, alias="sourceId")
    companion_spec_name: str | None = Field(default=None, alias="companionSpecName", max_length=255)
    companion_spec_version: str | None = Field(
        default=None, alias="companionSpecVersion", max_length=100
    )


class OPCUANodeSetResponse(BaseModel):
    """OPC UA NodeSet summary."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    source_id: UUID | None = None
    namespace_uri: str
    nodeset_version: str | None = None
    publication_date: date | None = None
    companion_spec_name: str | None = None
    companion_spec_version: str | None = None
    nodeset_file_ref: str
    companion_spec_file_ref: str | None = None
    hash_sha256: str
    parsed_summary_json: dict[str, Any]
    node_count: int = 0
    created_by: str
    created_at: datetime
    updated_at: datetime


class OPCUANodeSetDetailResponse(OPCUANodeSetResponse):
    """NodeSet with full parsed node graph (for detail endpoint)."""

    parsed_node_graph: dict[str, Any] = Field(default_factory=dict)


class OPCUANodeSetListResponse(BaseModel):
    """Paginated list of OPC UA nodesets."""

    items: list[OPCUANodeSetResponse]
    total: int


class NodeSearchResult(BaseModel):
    """Single node from a parsed node graph search."""

    node_id: str = Field(alias="nodeId")
    browse_name: str = Field(alias="browseName")
    node_class: str = Field(alias="nodeClass")
    data_type: str | None = Field(default=None, alias="dataType")
    description: str | None = None
    engineering_unit: str | None = Field(default=None, alias="engineeringUnit")
    parent_node_id: str | None = Field(default=None, alias="parentNodeId")


# ---------------------------------------------------------------------------
# OPC UA Mapping
# ---------------------------------------------------------------------------


class OPCUAMappingCreate(BaseModel):
    """Create a new OPC UA → AAS/EPCIS mapping."""

    model_config = ConfigDict(populate_by_name=True)

    source_id: UUID = Field(alias="sourceId")
    nodeset_id: UUID | None = Field(default=None, alias="nodesetId")
    mapping_type: OPCUAMappingType = Field(alias="mappingType")
    opcua_node_id: str = Field(alias="opcuaNodeId", min_length=1)
    opcua_browse_path: str | None = Field(default=None, alias="opcuaBrowsePath")
    opcua_datatype: str | None = Field(default=None, alias="opcuaDatatype")
    sampling_interval_ms: int | None = Field(default=None, alias="samplingIntervalMs", ge=50)
    # DPP binding
    dpp_binding_mode: DPPBindingMode = Field(
        default=DPPBindingMode.BY_DPP_ID, alias="dppBindingMode"
    )
    dpp_id: UUID | None = Field(default=None, alias="dppId")
    asset_id_query: dict[str, Any] | None = Field(default=None, alias="assetIdQuery")
    # AAS target
    target_template_key: str | None = Field(default=None, alias="targetTemplateKey")
    target_submodel_id: str | None = Field(default=None, alias="targetSubmodelId")
    target_aas_path: str | None = Field(default=None, alias="targetAasPath")
    patch_op: str | None = Field(default=None, alias="patchOp")
    value_transform_expr: str | None = Field(default=None, alias="valueTransformExpr")
    unit_hint: str | None = Field(default=None, alias="unitHint")
    # SAMM
    samm_aspect_urn: str | None = Field(default=None, alias="sammAspectUrn")
    samm_property: str | None = Field(default=None, alias="sammProperty")
    samm_version: str | None = Field(default=None, alias="sammVersion")
    # EPCIS (when mapping_type=EPCIS_EVENT)
    epcis_event_type: str | None = Field(default=None, alias="epcisEventType")
    epcis_biz_step: str | None = Field(default=None, alias="epcisBizStep")
    epcis_disposition: str | None = Field(default=None, alias="epcisDisposition")
    epcis_action: str | None = Field(default=None, alias="epcisAction")
    epcis_read_point: str | None = Field(default=None, alias="epcisReadPoint")
    epcis_biz_location: str | None = Field(default=None, alias="epcisBizLocation")
    epcis_source_event_id_template: str | None = Field(
        default=None, alias="epcisSourceEventIdTemplate"
    )
    is_enabled: bool = Field(default=True, alias="isEnabled")


class OPCUAMappingUpdate(BaseModel):
    """Partial update for an OPC UA mapping."""

    model_config = ConfigDict(populate_by_name=True)

    nodeset_id: UUID | None = Field(default=None, alias="nodesetId")
    mapping_type: OPCUAMappingType | None = Field(default=None, alias="mappingType")
    opcua_node_id: str | None = Field(default=None, alias="opcuaNodeId")
    opcua_browse_path: str | None = Field(default=None, alias="opcuaBrowsePath")
    opcua_datatype: str | None = Field(default=None, alias="opcuaDatatype")
    sampling_interval_ms: int | None = Field(default=None, alias="samplingIntervalMs", ge=50)
    dpp_binding_mode: DPPBindingMode | None = Field(default=None, alias="dppBindingMode")
    dpp_id: UUID | None = Field(default=None, alias="dppId")
    asset_id_query: dict[str, Any] | None = Field(default=None, alias="assetIdQuery")
    target_template_key: str | None = Field(default=None, alias="targetTemplateKey")
    target_submodel_id: str | None = Field(default=None, alias="targetSubmodelId")
    target_aas_path: str | None = Field(default=None, alias="targetAasPath")
    patch_op: str | None = Field(default=None, alias="patchOp")
    value_transform_expr: str | None = Field(default=None, alias="valueTransformExpr")
    unit_hint: str | None = Field(default=None, alias="unitHint")
    samm_aspect_urn: str | None = Field(default=None, alias="sammAspectUrn")
    samm_property: str | None = Field(default=None, alias="sammProperty")
    samm_version: str | None = Field(default=None, alias="sammVersion")
    epcis_event_type: str | None = Field(default=None, alias="epcisEventType")
    epcis_biz_step: str | None = Field(default=None, alias="epcisBizStep")
    epcis_disposition: str | None = Field(default=None, alias="epcisDisposition")
    epcis_action: str | None = Field(default=None, alias="epcisAction")
    epcis_read_point: str | None = Field(default=None, alias="epcisReadPoint")
    epcis_biz_location: str | None = Field(default=None, alias="epcisBizLocation")
    epcis_source_event_id_template: str | None = Field(
        default=None, alias="epcisSourceEventIdTemplate"
    )
    is_enabled: bool | None = Field(default=None, alias="isEnabled")


class OPCUAMappingResponse(BaseModel):
    """OPC UA mapping detail."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    source_id: UUID
    nodeset_id: UUID | None = None
    mapping_type: OPCUAMappingType
    opcua_node_id: str
    opcua_browse_path: str | None = None
    opcua_datatype: str | None = None
    sampling_interval_ms: int | None = None
    dpp_binding_mode: DPPBindingMode
    dpp_id: UUID | None = None
    asset_id_query: dict[str, Any] | None = None
    target_template_key: str | None = None
    target_submodel_id: str | None = None
    target_aas_path: str | None = None
    patch_op: str | None = None
    value_transform_expr: str | None = None
    unit_hint: str | None = None
    samm_aspect_urn: str | None = None
    samm_property: str | None = None
    samm_version: str | None = None
    epcis_event_type: str | None = None
    epcis_biz_step: str | None = None
    epcis_disposition: str | None = None
    epcis_action: str | None = None
    epcis_read_point: str | None = None
    epcis_biz_location: str | None = None
    epcis_source_event_id_template: str | None = None
    is_enabled: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class OPCUAMappingListResponse(BaseModel):
    """Paginated list of OPC UA mappings."""

    items: list[OPCUAMappingResponse]
    total: int


# ---------------------------------------------------------------------------
# Mapping validation & dry-run
# ---------------------------------------------------------------------------


class MappingValidationResult(BaseModel):
    """Result of validating a mapping's configuration."""

    model_config = ConfigDict(populate_by_name=True)

    is_valid: bool = Field(alias="isValid")
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DryRunRequest(BaseModel):
    """Optional input for dry-run: override the DPP revision JSON."""

    model_config = ConfigDict(populate_by_name=True)

    revision_json: dict[str, Any] | None = Field(default=None, alias="revisionJson")


class DryRunDiffEntry(BaseModel):
    """Single diff entry from a dry-run patch preview."""

    model_config = ConfigDict(populate_by_name=True)

    op: str
    path: str
    old_value: Any | None = Field(default=None, alias="oldValue")
    new_value: Any | None = Field(default=None, alias="newValue")


class MappingDryRunResult(BaseModel):
    """Result of a mapping dry-run against a DPP revision."""

    model_config = ConfigDict(populate_by_name=True)

    mapping_id: UUID = Field(alias="mappingId")
    dpp_id: UUID | None = Field(default=None, alias="dppId")
    diff: list[DryRunDiffEntry] = Field(default_factory=list)
    applied_value: Any | None = Field(default=None, alias="appliedValue")
    transform_output: Any | None = Field(default=None, alias="transformOutput")


# ---------------------------------------------------------------------------
# Dataspace Publication
# ---------------------------------------------------------------------------


class DataspacePublishRequest(BaseModel):
    """Request to publish a DPP to a dataspace (DTR + EDC)."""

    model_config = ConfigDict(populate_by_name=True)

    dpp_id: UUID = Field(alias="dppId")
    target: str = Field(default="catena-x", description="Target ecosystem")


class DataspacePublicationJobResponse(BaseModel):
    """Dataspace publication job summary."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    dpp_id: UUID
    status: str
    target: str
    artifact_refs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class DataspacePublicationJobListResponse(BaseModel):
    """Paginated list of publication jobs."""

    items: list[DataspacePublicationJobResponse]
    total: int
