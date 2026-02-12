"""Runtime adapter abstraction for dataspace connector implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.modules.connectors.catenax.dtr_client import DTRClient, DTRConfig
from app.modules.connectors.catenax.mapping import build_shell_descriptor
from app.modules.connectors.edc.asset_mapper import map_dpp_to_edc_asset
from app.modules.connectors.edc.client import EDCConfig, EDCManagementClient
from app.modules.connectors.edc.health import check_edc_health
from app.modules.connectors.edc.models import ContractDefinition, NegotiationState, TransferProcess
from app.modules.connectors.edc.policy_builder import build_access_policy, build_usage_policy


@dataclass(slots=True)
class RuntimeConnectorContext:
    """Runtime-ready connector config with resolved secret values."""

    connector_id: str
    runtime: str
    participant_id: str
    runtime_config: dict[str, Any]
    resolved_secrets: dict[str, str]


@dataclass(slots=True)
class PublicationRuntimeResult:
    """Result of asset publication in a connector runtime."""

    asset_id: str
    access_policy_id: str | None
    usage_policy_id: str | None
    contract_definition_id: str | None


class ConnectorRuntimeAdapter(Protocol):
    """Adapter contract for runtime-specific dataspace operations."""

    async def validate(self, context: RuntimeConnectorContext) -> dict[str, Any]:
        """Validate connector runtime connectivity and readiness."""

    async def publish_asset(
        self,
        *,
        context: RuntimeConnectorContext,
        dpp: Any,
        revision: Any,
        policy_template: dict[str, Any] | None = None,
    ) -> PublicationRuntimeResult:
        """Publish a DPP asset to the runtime."""

    async def query_catalog(
        self,
        *,
        context: RuntimeConnectorContext,
        connector_address: str,
        protocol: str,
        query_spec: dict[str, Any],
    ) -> dict[str, Any]:
        """Query remote catalog entries through the runtime."""

    async def initiate_negotiation(
        self,
        *,
        context: RuntimeConnectorContext,
        connector_address: str,
        offer_id: str,
        asset_id: str,
        policy: dict[str, Any],
    ) -> NegotiationState:
        """Start a contract negotiation."""

    async def get_negotiation(
        self,
        *,
        context: RuntimeConnectorContext,
        negotiation_id: str,
    ) -> NegotiationState:
        """Fetch contract negotiation state."""

    async def initiate_transfer(
        self,
        *,
        context: RuntimeConnectorContext,
        connector_address: str,
        contract_agreement_id: str,
        asset_id: str,
        data_destination: dict[str, Any],
    ) -> TransferProcess:
        """Start a transfer process."""

    async def get_transfer(
        self,
        *,
        context: RuntimeConnectorContext,
        transfer_id: str,
    ) -> TransferProcess:
        """Fetch transfer process state."""


class EDCAdapter:
    """EDC implementation of the runtime adapter contract."""

    def _edc_config(self, context: RuntimeConnectorContext) -> EDCConfig:
        runtime_config = context.runtime_config
        api_key = self._resolve_secret(
            context=context,
            secret_ref=runtime_config.get("management_api_key_secret_ref"),
        )
        return EDCConfig(
            management_url=str(runtime_config.get("management_url", "")),
            api_key=api_key or "",
            dsp_endpoint=str(runtime_config.get("dsp_endpoint") or ""),
            participant_id=context.participant_id,
        )

    @staticmethod
    def _resolve_secret(
        *,
        context: RuntimeConnectorContext,
        secret_ref: str | None,
    ) -> str | None:
        if not secret_ref:
            return None
        return context.resolved_secrets.get(secret_ref)

    async def validate(self, context: RuntimeConnectorContext) -> dict[str, Any]:
        client = EDCManagementClient(self._edc_config(context))
        try:
            return await check_edc_health(client)
        finally:
            await client.close()

    async def publish_asset(
        self,
        *,
        context: RuntimeConnectorContext,
        dpp: Any,
        revision: Any,
        policy_template: dict[str, Any] | None = None,
    ) -> PublicationRuntimeResult:
        runtime_config = context.runtime_config
        public_api_base_url = str(
            runtime_config.get("public_api_base_url") or "https://dpp-platform.dev/api/v1/public"
        )
        client = EDCManagementClient(self._edc_config(context))

        try:
            edc_asset = map_dpp_to_edc_asset(dpp, revision, public_api_base_url)

            existing = await client.get_asset(edc_asset.asset_id)
            if existing:
                await client.delete_asset(edc_asset.asset_id)

            await client.create_asset(edc_asset)

            policy_input = policy_template or runtime_config

            access_policy_id = f"access-{edc_asset.asset_id}"
            await client.create_policy(build_access_policy(access_policy_id, policy_input))

            usage_policy_id = f"usage-{edc_asset.asset_id}"
            await client.create_policy(build_usage_policy(usage_policy_id, policy_input))

            contract_definition_id = f"contract-{edc_asset.asset_id}"
            contract_definition = ContractDefinition(
                contract_id=contract_definition_id,
                access_policy_id=access_policy_id,
                contract_policy_id=usage_policy_id,
                asset_selector={
                    "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
                    "operator": "=",
                    "operandRight": edc_asset.asset_id,
                },
            )
            await client.create_contract_definition(contract_definition)

            return PublicationRuntimeResult(
                asset_id=edc_asset.asset_id,
                access_policy_id=access_policy_id,
                usage_policy_id=usage_policy_id,
                contract_definition_id=contract_definition_id,
            )
        finally:
            await client.close()

    async def query_catalog(
        self,
        *,
        context: RuntimeConnectorContext,
        connector_address: str,
        protocol: str,
        query_spec: dict[str, Any],
    ) -> dict[str, Any]:
        client = EDCManagementClient(self._edc_config(context))
        try:
            return await client.query_catalog(
                connector_address=connector_address,
                protocol=protocol,
                query_spec=query_spec,
            )
        finally:
            await client.close()

    async def initiate_negotiation(
        self,
        *,
        context: RuntimeConnectorContext,
        connector_address: str,
        offer_id: str,
        asset_id: str,
        policy: dict[str, Any],
    ) -> NegotiationState:
        client = EDCManagementClient(self._edc_config(context))
        try:
            return await client.initiate_negotiation(
                connector_address=connector_address,
                offer_id=offer_id,
                asset_id=asset_id,
                policy=policy,
            )
        finally:
            await client.close()

    async def get_negotiation(
        self,
        *,
        context: RuntimeConnectorContext,
        negotiation_id: str,
    ) -> NegotiationState:
        client = EDCManagementClient(self._edc_config(context))
        try:
            return await client.get_negotiation(negotiation_id=negotiation_id)
        finally:
            await client.close()

    async def initiate_transfer(
        self,
        *,
        context: RuntimeConnectorContext,
        connector_address: str,
        contract_agreement_id: str,
        asset_id: str,
        data_destination: dict[str, Any],
    ) -> TransferProcess:
        client = EDCManagementClient(self._edc_config(context))
        try:
            return await client.initiate_transfer(
                connector_address=connector_address,
                contract_agreement_id=contract_agreement_id,
                asset_id=asset_id,
                data_destination=data_destination,
            )
        finally:
            await client.close()

    async def get_transfer(
        self,
        *,
        context: RuntimeConnectorContext,
        transfer_id: str,
    ) -> TransferProcess:
        client = EDCManagementClient(self._edc_config(context))
        try:
            return await client.get_transfer(transfer_id=transfer_id)
        finally:
            await client.close()


class CatenaXDTRAdapter:
    """Catena-X DTR implementation for registry-oriented connector flows."""

    @staticmethod
    def _resolve_secret(
        *,
        context: RuntimeConnectorContext,
        secret_ref: str | None,
    ) -> str | None:
        if not secret_ref:
            return None
        return context.resolved_secrets.get(secret_ref)

    def _dtr_config(self, context: RuntimeConnectorContext) -> DTRConfig:
        runtime_config = context.runtime_config
        return DTRConfig(
            base_url=str(runtime_config.get("dtr_base_url", "")),
            auth_type=str(runtime_config.get("auth_type") or "token"),
            client_id=(
                str(runtime_config.get("client_id"))
                if runtime_config.get("client_id") is not None
                else None
            ),
            client_secret=self._resolve_secret(
                context=context,
                secret_ref=runtime_config.get("client_secret_secret_ref"),
            ),
            token=self._resolve_secret(
                context=context,
                secret_ref=runtime_config.get("token_secret_ref"),
            ),
            bpn=(
                str(runtime_config.get("bpn"))
                if runtime_config.get("bpn") is not None
                else None
            ),
        )

    async def validate(self, context: RuntimeConnectorContext) -> dict[str, Any]:
        client = DTRClient(self._dtr_config(context))
        try:
            result = await client.test_connection()
        finally:
            await client.close()

        if result.get("status") == "connected":
            return {
                **result,
                "status": "ok",
                "runtime": "catena_x_dtr",
            }
        return {
            **result,
            "status": "error",
            "runtime": "catena_x_dtr",
            "error_message": result.get("error_message", "DTR connection failed"),
        }

    async def publish_asset(
        self,
        *,
        context: RuntimeConnectorContext,
        dpp: Any,
        revision: Any,
        policy_template: dict[str, Any] | None = None,  # noqa: ARG002 - unused for DTR
    ) -> PublicationRuntimeResult:
        runtime_config = context.runtime_config
        descriptor = build_shell_descriptor(
            dpp=dpp,
            revision=revision,
            submodel_base_url=str(runtime_config.get("submodel_base_url", "")),
            edc_dsp_endpoint=(
                str(runtime_config["edc_dsp_endpoint"])
                if runtime_config.get("edc_dsp_endpoint") is not None
                else None
            ),
        )

        client = DTRClient(self._dtr_config(context))
        try:
            existing = await client.get_shell(descriptor.id)
            if existing:
                await client.update_shell(descriptor.id, descriptor)
            else:
                await client.register_shell(descriptor)
        finally:
            await client.close()

        return PublicationRuntimeResult(
            asset_id=descriptor.id,
            access_policy_id=None,
            usage_policy_id=None,
            contract_definition_id=None,
        )

    async def query_catalog(
        self,
        *,
        context: RuntimeConnectorContext,  # noqa: ARG002
        connector_address: str,  # noqa: ARG002
        protocol: str,  # noqa: ARG002
        query_spec: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        raise NotImplementedError("catena_x_dtr runtime does not support catalog query")

    async def initiate_negotiation(
        self,
        *,
        context: RuntimeConnectorContext,  # noqa: ARG002
        connector_address: str,  # noqa: ARG002
        offer_id: str,  # noqa: ARG002
        asset_id: str,  # noqa: ARG002
        policy: dict[str, Any],  # noqa: ARG002
    ) -> NegotiationState:
        raise NotImplementedError("catena_x_dtr runtime does not support contract negotiation")

    async def get_negotiation(
        self,
        *,
        context: RuntimeConnectorContext,  # noqa: ARG002
        negotiation_id: str,  # noqa: ARG002
    ) -> NegotiationState:
        raise NotImplementedError("catena_x_dtr runtime does not support contract negotiation")

    async def initiate_transfer(
        self,
        *,
        context: RuntimeConnectorContext,  # noqa: ARG002
        connector_address: str,  # noqa: ARG002
        contract_agreement_id: str,  # noqa: ARG002
        asset_id: str,  # noqa: ARG002
        data_destination: dict[str, Any],  # noqa: ARG002
    ) -> TransferProcess:
        raise NotImplementedError("catena_x_dtr runtime does not support transfer process")

    async def get_transfer(
        self,
        *,
        context: RuntimeConnectorContext,  # noqa: ARG002
        transfer_id: str,  # noqa: ARG002
    ) -> TransferProcess:
        raise NotImplementedError("catena_x_dtr runtime does not support transfer process")


def get_runtime_adapter(runtime: str) -> ConnectorRuntimeAdapter:
    """Resolve runtime adapter implementation for a connector runtime."""
    if runtime == "edc":
        return EDCAdapter()
    if runtime == "catena_x_dtr":
        return CatenaXDTRAdapter()
    raise ValueError(f"Unsupported runtime adapter: {runtime}")
