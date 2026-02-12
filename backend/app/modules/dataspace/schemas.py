"""Pydantic schemas for dataspace control-plane APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SecretValueWrite(BaseModel):
    """Secret value submitted for a secret reference."""

    secret_ref: str = Field(min_length=1, max_length=255)
    value: str = Field(min_length=1, max_length=8192)

    model_config = ConfigDict(extra="forbid")


class EDCRuntimeConfig(BaseModel):
    """Strict EDC runtime configuration for dataspace connectors."""

    management_url: str = Field(min_length=1, max_length=1024)
    dsp_endpoint: str | None = Field(default=None, max_length=1024)
    management_api_key_secret_ref: str | None = Field(default=None, max_length=255)
    public_api_base_url: str | None = Field(default=None, max_length=1024)
    provider_connector_address: str | None = Field(default=None, max_length=1024)
    protocol: str = Field(default="dataspace-protocol-http", max_length=128)
    allowed_bpns: list[str] = Field(default_factory=list)
    data_destination_type: str = Field(default="HttpProxy", max_length=128)
    data_destination_properties: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class CatenaXDTRRuntimeConfig(BaseModel):
    """Strict Catena-X DTR runtime config for registry-oriented flows."""

    dtr_base_url: str = Field(min_length=1, max_length=1024)
    submodel_base_url: str = Field(min_length=1, max_length=1024)
    auth_type: Literal["token", "oidc"] = "token"
    bpn: str | None = Field(default=None, max_length=255)
    token_secret_ref: str | None = Field(default=None, max_length=255)
    client_id: str | None = Field(default=None, max_length=255)
    client_secret_secret_ref: str | None = Field(default=None, max_length=255)
    edc_dsp_endpoint: str | None = Field(default=None, max_length=1024)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_auth_fields(self) -> CatenaXDTRRuntimeConfig:
        if self.auth_type == "token" and not self.token_secret_ref:
            raise ValueError("token_secret_ref is required when auth_type is token")
        if self.auth_type == "oidc":
            if not self.client_id:
                raise ValueError("client_id is required when auth_type is oidc")
            if not self.client_secret_secret_ref:
                raise ValueError("client_secret_secret_ref is required when auth_type is oidc")
        return self


RuntimeConfig = EDCRuntimeConfig | CatenaXDTRRuntimeConfig


class DataspaceConnectorCreateRequest(BaseModel):
    """Create request for a dataspace connector instance."""

    name: str = Field(min_length=1, max_length=255)
    runtime: Literal["edc", "catena_x_dtr"] = "edc"
    participant_id: str = Field(min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    runtime_config: RuntimeConfig
    secrets: list[SecretValueWrite] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_runtime_config(self) -> DataspaceConnectorCreateRequest:
        if self.runtime == "edc" and not isinstance(self.runtime_config, EDCRuntimeConfig):
            raise ValueError("runtime_config must be EDCRuntimeConfig when runtime is edc")
        if self.runtime == "catena_x_dtr" and not isinstance(
            self.runtime_config, CatenaXDTRRuntimeConfig
        ):
            raise ValueError(
                "runtime_config must be CatenaXDTRRuntimeConfig when runtime is catena_x_dtr"
            )
        return self


class DataspaceConnectorUpdateRequest(BaseModel):
    """Patch request for dataspace connector updates."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    participant_id: str | None = Field(default=None, min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    status: Literal["active", "disabled", "error"] | None = None
    runtime_config: RuntimeConfig | None = None
    secrets: list[SecretValueWrite] | None = None

    model_config = ConfigDict(extra="forbid")


class DataspaceConnectorResponse(BaseModel):
    """API response model for a dataspace connector."""

    id: UUID
    name: str
    runtime: str
    participant_id: str
    display_name: str | None
    status: str
    runtime_config: RuntimeConfig
    secret_refs: list[str]
    created_by_subject: str
    last_validated_at: datetime | None
    last_validation_result: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DataspaceConnectorListResponse(BaseModel):
    """List response for dataspace connectors."""

    connectors: list[DataspaceConnectorResponse]
    count: int


class ConnectorValidationResponse(BaseModel):
    """Connector validation outcome."""

    status: Literal["ok", "error"]
    details: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)


class AssetPublishRequest(BaseModel):
    """Request payload for dataspace asset publication."""

    dpp_id: UUID
    connector_id: UUID
    policy_template_id: UUID | None = None
    revision_id: UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=255)

    model_config = ConfigDict(extra="forbid")


class AssetPublicationResponse(BaseModel):
    """Response payload for published dataspace assets."""

    id: UUID
    status: str
    dpp_id: UUID
    connector_id: UUID
    asset_id: str
    access_policy_id: str | None = None
    usage_policy_id: str | None = None
    contract_definition_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AssetPublicationListResponse(BaseModel):
    """List response for asset publications."""

    items: list[AssetPublicationResponse]
    count: int


class CatalogQueryRequest(BaseModel):
    """Request payload for connector catalog queries."""

    connector_id: UUID
    connector_address: str = Field(min_length=1, max_length=1024)
    protocol: str = Field(default="dataspace-protocol-http", max_length=128)
    query_spec: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class CatalogEntry(BaseModel):
    """Catalog entry item returned from runtime adapters."""

    id: str
    title: str | None = None
    description: str | None = None
    asset_id: str | None = None
    policy: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None


class CatalogQueryResponse(BaseModel):
    """Response payload for catalog query operations."""

    status: Literal["ok", "error"]
    entries: list[CatalogEntry] = Field(default_factory=list)
    raw: dict[str, Any] | None = None
    error_message: str | None = None


class NegotiationCreateRequest(BaseModel):
    """Request payload for contract negotiation creation."""

    connector_id: UUID
    publication_id: UUID | None = None
    connector_address: str = Field(min_length=1, max_length=1024)
    offer_id: str = Field(min_length=1, max_length=255)
    asset_id: str = Field(min_length=1, max_length=255)
    policy: dict[str, Any]
    idempotency_key: str | None = Field(default=None, max_length=255)

    model_config = ConfigDict(extra="forbid")


class NegotiationResponse(BaseModel):
    """Response payload for negotiation state."""

    id: UUID
    connector_id: UUID
    publication_id: UUID | None = None
    negotiation_id: str
    state: str
    contract_agreement_id: str | None = None
    created_at: datetime
    updated_at: datetime


class NegotiationListResponse(BaseModel):
    """List response for negotiation records."""

    items: list[NegotiationResponse]
    count: int


class TransferCreateRequest(BaseModel):
    """Request payload for transfer process creation."""

    connector_id: UUID
    negotiation_id: UUID | None = None
    connector_address: str = Field(min_length=1, max_length=1024)
    contract_agreement_id: str = Field(min_length=1, max_length=255)
    asset_id: str = Field(min_length=1, max_length=255)
    data_destination: dict[str, Any]
    idempotency_key: str | None = Field(default=None, max_length=255)

    model_config = ConfigDict(extra="forbid")


class TransferResponse(BaseModel):
    """Response payload for transfer process state."""

    id: UUID
    connector_id: UUID
    negotiation_id: UUID | None = None
    transfer_id: str
    state: str
    data_destination: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class TransferListResponse(BaseModel):
    """List response for transfer records."""

    items: list[TransferResponse]
    count: int


class ConformanceRunRequest(BaseModel):
    """Request payload for starting a conformance run."""

    connector_id: UUID | None = None
    profile: str = Field(default="dsp-tck", max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ConformanceRunResponse(BaseModel):
    """Response payload for conformance run metadata."""

    id: UUID
    connector_id: UUID | None = None
    run_type: str
    status: str
    request_payload: dict[str, Any]
    result_payload: dict[str, Any] | None = None
    artifact_url: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConformanceRunListResponse(BaseModel):
    """List response for conformance runs."""

    items: list[ConformanceRunResponse]
    count: int


class PolicyTemplateCreateRequest(BaseModel):
    """Create request for dataspace policy templates."""

    name: str = Field(min_length=1, max_length=255)
    version: str = Field(default="1", min_length=1, max_length=64)
    description: str | None = None
    policy: dict[str, Any]

    model_config = ConfigDict(extra="forbid")


class PolicyTemplateUpdateRequest(BaseModel):
    """Update request for mutable policy-template fields."""

    description: str | None = None
    policy: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


class PolicyTemplateResponse(BaseModel):
    """Response model for dataspace policy templates."""

    id: UUID
    name: str
    version: str
    state: str
    description: str | None
    policy: dict[str, Any]
    created_by_subject: str
    approved_by_subject: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PolicyTemplateListResponse(BaseModel):
    """List response for policy templates."""

    templates: list[PolicyTemplateResponse]
    count: int


class CredentialStatusResponse(BaseModel):
    """Credential status in evidence reports."""

    exists: bool
    revoked: bool | None = None
    issuer_did: str | None = None
    issuance_date: datetime | None = None
    expiration_date: datetime | None = None


class RegulatoryEvidenceResponse(BaseModel):
    """Aggregated regulatory/dataspace evidence for a DPP."""

    dpp_id: UUID
    profile: str
    generated_at: datetime
    compliance_reports: list[dict[str, Any]]
    credential_status: CredentialStatusResponse
    resolver_links: list[dict[str, Any]]
    shell_descriptors: list[dict[str, Any]]
    dataspace_publications: list[dict[str, Any]]
    dataspace_negotiations: list[dict[str, Any]]
    dataspace_transfers: list[dict[str, Any]]
    dataspace_conformance_runs: list[dict[str, Any]]


class PolicyTemplateManifest(BaseModel):
    """Manifest representation of a dataspace policy template."""

    name: str = Field(min_length=1, max_length=255)
    version: str = Field(default="1", min_length=1, max_length=64)
    state: Literal["draft", "approved", "active", "superseded"] = "draft"
    policy: dict[str, Any]
    description: str | None = None

    model_config = ConfigDict(extra="forbid")


class ConnectorManifest(BaseModel):
    """Config-as-code manifest for connector and policy provisioning."""

    connector: DataspaceConnectorCreateRequest
    policy_templates: list[PolicyTemplateManifest] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ManifestChange(BaseModel):
    """Single manifest diff/apply change entry."""

    resource: str
    action: Literal["create", "update", "noop"]
    field: str | None = None
    old_value: Any | None = None
    new_value: Any | None = None


class ManifestDiffResponse(BaseModel):
    """Response payload for manifest diff preview."""

    has_changes: bool
    changes: list[ManifestChange]


class ManifestApplyResponse(BaseModel):
    """Response payload for manifest apply operations."""

    status: Literal["applied", "noop"]
    connector_id: UUID
    applied_changes: list[ManifestChange]
