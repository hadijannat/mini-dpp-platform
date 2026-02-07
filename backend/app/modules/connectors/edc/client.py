"""
EDC Management API v3 client.

Mirrors the DTRClient pattern: persistent httpx.AsyncClient, dataclass
config object, structured logging, and explicit ``close()`` lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import httpx

from app.core.logging import get_logger
from app.modules.connectors.edc.models import (
    ContractDefinition,
    EDCAsset,
    NegotiationState,
    PolicyDefinition,
    TransferProcess,
)

logger = get_logger(__name__)


@dataclass
class EDCConfig:
    """Configuration for connecting to a Tractus-X EDC controlplane."""

    management_url: str  # e.g. http://edc-controlplane:19193/management
    api_key: str = ""
    dsp_endpoint: str = ""  # DSP protocol endpoint URL
    participant_id: str = ""  # BPN of this EDC participant


class EDCManagementClient:
    """
    Client for the Tractus-X EDC Management API v3.

    Uses ``X-Api-Key`` header authentication and targets the ``/management/v3``
    path prefix.
    """

    def __init__(self, config: EDCConfig) -> None:
        self._config = config
        self._http_client: httpx.AsyncClient | None = None

    def _validate_config(self) -> None:
        base = (self._config.management_url or "").strip()
        if not base:
            raise ValueError("EDC management URL is required")
        self._config.management_url = base.rstrip("/")

    async def _get_client(self) -> httpx.AsyncClient:
        """Return (or lazily create) the authenticated HTTP client."""
        if self._http_client is None:
            self._validate_config()
            headers: dict[str, str] = {
                "Content-Type": "application/json",
            }
            if self._config.api_key:
                headers["X-Api-Key"] = self._config.api_key

            self._http_client = httpx.AsyncClient(
                base_url=self._config.management_url,
                headers=headers,
                timeout=30.0,
            )
        return self._http_client

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    async def create_asset(self, asset: EDCAsset) -> dict[str, Any]:
        """Create an asset in the EDC catalog."""
        client = await self._get_client()

        logger.info(
            "edc_creating_asset",
            asset_id=asset.asset_id,
        )

        response = await client.post(
            "/management/v3/assets",
            json=asset.to_edc_payload(),
        )
        response.raise_for_status()

        result = cast(dict[str, Any], response.json())

        logger.info(
            "edc_asset_created",
            asset_id=asset.asset_id,
            edc_response_id=result.get("@id"),
        )

        return result

    async def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        """Retrieve an asset by ID.  Returns ``None`` if not found."""
        client = await self._get_client()

        try:
            response = await client.get(f"/management/v3/assets/{asset_id}")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    async def delete_asset(self, asset_id: str) -> bool:
        """Delete an asset.  Returns ``True`` if deleted or already absent."""
        client = await self._get_client()
        response = await client.delete(f"/management/v3/assets/{asset_id}")
        return response.status_code in (200, 204, 404)

    # ------------------------------------------------------------------
    # Policies
    # ------------------------------------------------------------------

    async def create_policy(self, policy: PolicyDefinition) -> dict[str, Any]:
        """Create a policy definition."""
        client = await self._get_client()

        logger.info("edc_creating_policy", policy_id=policy.policy_id)

        response = await client.post(
            "/management/v3/policydefinitions",
            json=policy.to_edc_payload(),
        )
        response.raise_for_status()

        result = cast(dict[str, Any], response.json())

        logger.info(
            "edc_policy_created",
            policy_id=policy.policy_id,
            edc_response_id=result.get("@id"),
        )

        return result

    # ------------------------------------------------------------------
    # Contract Definitions
    # ------------------------------------------------------------------

    async def create_contract_definition(
        self, contract: ContractDefinition
    ) -> dict[str, Any]:
        """Create a contract definition linking assets to policies."""
        client = await self._get_client()

        logger.info(
            "edc_creating_contract_definition",
            contract_id=contract.contract_id,
        )

        response = await client.post(
            "/management/v3/contractdefinitions",
            json=contract.to_edc_payload(),
        )
        response.raise_for_status()

        result = cast(dict[str, Any], response.json())

        logger.info(
            "edc_contract_definition_created",
            contract_id=contract.contract_id,
            edc_response_id=result.get("@id"),
        )

        return result

    # ------------------------------------------------------------------
    # Contract Negotiations
    # ------------------------------------------------------------------

    async def initiate_negotiation(
        self,
        connector_address: str,
        offer_id: str,
        asset_id: str,
        policy: dict[str, Any],
    ) -> NegotiationState:
        """Start a contract negotiation with a counter-party EDC."""
        client = await self._get_client()

        body: dict[str, Any] = {
            "@context": {"edc": "https://w3id.org/edc/v0.0.1/ns/"},
            "connectorAddress": connector_address,
            "protocol": "dataspace-protocol-http",
            "offer": {
                "offerId": offer_id,
                "assetId": asset_id,
                "policy": policy,
            },
        }

        response = await client.post(
            "/management/v3/contractnegotiations",
            json=body,
        )
        response.raise_for_status()

        data = cast(dict[str, Any], response.json())
        return NegotiationState(
            negotiation_id=str(data.get("@id", "")),
            state=str(data.get("state", "INITIAL")),
            contract_agreement_id=data.get("contractAgreementId"),
        )

    async def get_negotiation(self, negotiation_id: str) -> NegotiationState:
        """Poll the state of a contract negotiation."""
        client = await self._get_client()

        response = await client.get(
            f"/management/v3/contractnegotiations/{negotiation_id}",
        )
        response.raise_for_status()

        data = cast(dict[str, Any], response.json())
        return NegotiationState(
            negotiation_id=str(data.get("@id", "")),
            state=str(data.get("state", "")),
            contract_agreement_id=data.get("contractAgreementId"),
        )

    # ------------------------------------------------------------------
    # Transfer Processes
    # ------------------------------------------------------------------

    async def initiate_transfer(
        self,
        connector_address: str,
        contract_agreement_id: str,
        asset_id: str,
        data_destination: dict[str, Any],
    ) -> TransferProcess:
        """Start a data transfer process."""
        client = await self._get_client()

        body: dict[str, Any] = {
            "@context": {"edc": "https://w3id.org/edc/v0.0.1/ns/"},
            "connectorAddress": connector_address,
            "protocol": "dataspace-protocol-http",
            "contractId": contract_agreement_id,
            "assetId": asset_id,
            "dataDestination": data_destination,
        }

        response = await client.post(
            "/management/v3/transferprocesses",
            json=body,
        )
        response.raise_for_status()

        data = cast(dict[str, Any], response.json())
        return TransferProcess(
            transfer_id=str(data.get("@id", "")),
            state=str(data.get("state", "INITIAL")),
            data_destination=data_destination,
        )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def check_health(self) -> dict[str, Any]:
        """Hit the EDC health/readiness endpoint."""
        client = await self._get_client()

        try:
            response = await client.get("/api/check/health")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except httpx.HTTPStatusError as exc:
            return {
                "status": "error",
                "error_code": exc.response.status_code,
                "error_message": str(exc),
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_message": str(exc),
            }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
