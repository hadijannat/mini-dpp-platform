"""
Pydantic models for the Tractus-X EDC Management API v3 payloads.

These models map to the JSON-LD structures used by the EDC management
endpoints. Field names use snake_case locally and are serialized
to the EDC-expected format via aliases and custom serialization.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Data Address
# ---------------------------------------------------------------------------


class DataAddress(BaseModel):
    """EDC DataAddress pointing to the DPP public API."""

    type: str = "HttpData"
    base_url: str
    proxy_body: bool = False
    proxy_path: bool = True
    proxy_query_params: bool = True

    def to_edc_payload(self) -> dict[str, Any]:
        return {
            "@type": "DataAddress",
            "type": self.type,
            "baseUrl": self.base_url,
            "proxyBody": str(self.proxy_body).lower(),
            "proxyPath": str(self.proxy_path).lower(),
            "proxyQueryParams": str(self.proxy_query_params).lower(),
        }


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------


class EDCAsset(BaseModel):
    """EDC Asset with DataAddress."""

    asset_id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    data_address: DataAddress

    def to_edc_payload(self) -> dict[str, Any]:
        """Serialize to EDC Management API v3 create-asset request body."""
        return {
            "@context": {"edc": "https://w3id.org/edc/v0.0.1/ns/"},
            "@id": self.asset_id,
            "properties": self.properties,
            "dataAddress": self.data_address.to_edc_payload(),
        }


# ---------------------------------------------------------------------------
# ODRL Policy
# ---------------------------------------------------------------------------


class ODRLConstraint(BaseModel):
    """Single ODRL constraint (left operand / operator / right operand)."""

    left_operand: str
    operator: str
    right_operand: str

    def to_edc_payload(self) -> dict[str, Any]:
        return {
            "leftOperand": self.left_operand,
            "operator": self.operator,
            "rightOperand": self.right_operand,
        }


class ODRLPermission(BaseModel):
    """ODRL permission with optional constraints."""

    action: str = "use"
    constraints: list[ODRLConstraint] = Field(default_factory=list)

    def to_edc_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"action": self.action}
        if self.constraints:
            payload["constraint"] = {
                "and": [c.to_edc_payload() for c in self.constraints],
            }
        return payload


class ODRLPolicy(BaseModel):
    """ODRL policy expression."""

    permissions: list[ODRLPermission] = Field(default_factory=list)
    prohibitions: list[dict[str, Any]] = Field(default_factory=list)
    obligations: list[dict[str, Any]] = Field(default_factory=list)

    def to_edc_payload(self) -> dict[str, Any]:
        return {
            "@type": "odrl:Set",
            "permission": [p.to_edc_payload() for p in self.permissions],
            "prohibition": self.prohibitions,
            "obligation": self.obligations,
        }


# ---------------------------------------------------------------------------
# Policy Definition
# ---------------------------------------------------------------------------


class PolicyDefinition(BaseModel):
    """ODRL policy wrapper registered with EDC."""

    policy_id: str
    policy: ODRLPolicy

    def to_edc_payload(self) -> dict[str, Any]:
        return {
            "@context": {
                "odrl": "http://www.w3.org/ns/odrl/2/",
                "edc": "https://w3id.org/edc/v0.0.1/ns/",
            },
            "@id": self.policy_id,
            "policy": self.policy.to_edc_payload(),
        }


# ---------------------------------------------------------------------------
# Contract Definition
# ---------------------------------------------------------------------------


class ContractDefinition(BaseModel):
    """Links assets to access and contract policies."""

    contract_id: str
    access_policy_id: str
    contract_policy_id: str
    asset_selector: dict[str, Any] = Field(default_factory=dict)

    def to_edc_payload(self) -> dict[str, Any]:
        return {
            "@context": {"edc": "https://w3id.org/edc/v0.0.1/ns/"},
            "@id": self.contract_id,
            "accessPolicyId": self.access_policy_id,
            "contractPolicyId": self.contract_policy_id,
            "assetsSelector": self.asset_selector,
        }


# ---------------------------------------------------------------------------
# Negotiation & Transfer state
# ---------------------------------------------------------------------------


class NegotiationState(BaseModel):
    """Contract negotiation state returned by EDC."""

    negotiation_id: str
    state: str
    contract_agreement_id: str | None = None


class TransferProcess(BaseModel):
    """Data transfer process state returned by EDC."""

    transfer_id: str
    state: str
    data_destination: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Publish result (returned by the contract service)
# ---------------------------------------------------------------------------


class PublishResult(BaseModel):
    """Result of a publish-to-dataspace operation."""

    status: str  # "success" | "error"
    asset_id: str | None = None
    access_policy_id: str | None = None
    usage_policy_id: str | None = None
    contract_definition_id: str | None = None
    error_message: str | None = None
