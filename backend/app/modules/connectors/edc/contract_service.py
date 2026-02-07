"""
Publish-to-dataspace orchestration service.

Coordinates the full EDC publication flow:
  1. Create EDC asset
  2. Create access policy
  3. Create usage policy
  4. Create contract definition
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Connector, ConnectorStatus
from app.modules.connectors.edc.asset_mapper import map_dpp_to_edc_asset
from app.modules.connectors.edc.client import EDCConfig, EDCManagementClient
from app.modules.connectors.edc.models import ContractDefinition, PublishResult
from app.modules.connectors.edc.policy_builder import build_access_policy, build_usage_policy
from app.modules.dpps.service import DPPService

logger = get_logger(__name__)


class EDCContractService:
    """
    Orchestrates publishing a DPP to an Eclipse Dataspace Connector.

    The service creates an EDC asset, registers access and usage policies,
    and links them via a contract definition so data consumers can discover
    and negotiate access to the DPP through the dataspace.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._dpp_service = DPPService(session)

    async def publish_to_dataspace(
        self,
        dpp_id: UUID,
        connector_id: UUID,
        tenant_id: UUID,
    ) -> PublishResult:
        """
        Publish a DPP as an EDC asset with policies and contract definition.

        Args:
            dpp_id: ID of the DPP to publish.
            connector_id: ID of the connector configured for EDC.
            tenant_id: Tenant scope.

        Returns:
            A ``PublishResult`` describing the created resources or error.
        """
        # --- resolve connector ---
        connector = await self._get_connector(connector_id, tenant_id)
        if not connector:
            return PublishResult(
                status="error",
                error_message=f"Connector {connector_id} not found",
            )

        if connector.status != ConnectorStatus.ACTIVE:
            return PublishResult(
                status="error",
                error_message=f"Connector {connector_id} is not active",
            )

        # --- resolve DPP and published revision ---
        dpp = await self._dpp_service.get_dpp(dpp_id, tenant_id)
        if not dpp:
            return PublishResult(
                status="error",
                error_message=f"DPP {dpp_id} not found",
            )

        revision = await self._dpp_service.get_published_revision(dpp_id, tenant_id)
        if not revision:
            return PublishResult(
                status="error",
                error_message=f"DPP {dpp_id} has no published revision",
            )

        # --- build EDC client ---
        config = connector.config
        edc_config = EDCConfig(
            management_url=config.get("edc_management_url", ""),
            api_key=config.get("edc_management_api_key", ""),
            dsp_endpoint=config.get("edc_dsp_endpoint", ""),
            participant_id=config.get("edc_participant_id", ""),
        )
        client = EDCManagementClient(edc_config)

        try:
            return await self._execute_publish(
                client=client,
                dpp=dpp,
                revision=revision,
                connector=connector,
            )
        except Exception as exc:
            logger.error(
                "edc_publish_failed",
                dpp_id=str(dpp_id),
                connector_id=str(connector_id),
                error=str(exc),
            )
            return PublishResult(
                status="error",
                error_message=str(exc),
            )
        finally:
            await client.close()

    async def get_dataspace_status(
        self,
        dpp_id: UUID,
        connector_id: UUID,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """
        Check whether a DPP is registered in the EDC catalog.

        Returns a dict with ``registered`` (bool) and asset metadata.
        """
        connector = await self._get_connector(connector_id, tenant_id)
        if not connector:
            return {"registered": False, "error": "Connector not found"}

        config = connector.config
        edc_config = EDCConfig(
            management_url=config.get("edc_management_url", ""),
            api_key=config.get("edc_management_api_key", ""),
        )
        client = EDCManagementClient(edc_config)

        try:
            asset_id = f"dpp-{dpp_id}"
            asset = await client.get_asset(asset_id)

            if asset:
                return {"registered": True, "asset_id": asset_id, "asset": asset}
            return {"registered": False, "asset_id": asset_id}

        except Exception as exc:
            return {"registered": False, "error": str(exc)}
        finally:
            await client.close()

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    async def _get_connector(
        self, connector_id: UUID, tenant_id: UUID
    ) -> Connector | None:
        result = await self._session.execute(
            select(Connector).where(
                Connector.id == connector_id,
                Connector.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def _execute_publish(
        self,
        client: EDCManagementClient,
        dpp: Any,
        revision: Any,
        connector: Connector,
    ) -> PublishResult:
        """Run the four-step publish flow against the EDC management API."""
        config = connector.config
        public_api_base_url = config.get(
            "public_api_base_url",
            "https://dpp-platform.dev/api/v1/public",
        )

        # 1. Create EDC asset
        edc_asset = map_dpp_to_edc_asset(dpp, revision, public_api_base_url)

        # If asset already exists, delete first (idempotent re-publish)
        existing = await client.get_asset(edc_asset.asset_id)
        if existing:
            await client.delete_asset(edc_asset.asset_id)
            logger.info(
                "edc_asset_replaced",
                asset_id=edc_asset.asset_id,
            )

        await client.create_asset(edc_asset)

        # 2. Create access policy
        access_policy_id = f"access-{edc_asset.asset_id}"
        access_policy = build_access_policy(access_policy_id, config)
        await client.create_policy(access_policy)

        # 3. Create usage policy
        usage_policy_id = f"usage-{edc_asset.asset_id}"
        usage_policy = build_usage_policy(usage_policy_id, config)
        await client.create_policy(usage_policy)

        # 4. Create contract definition
        contract_id = f"contract-{edc_asset.asset_id}"
        contract_def = ContractDefinition(
            contract_id=contract_id,
            access_policy_id=access_policy_id,
            contract_policy_id=usage_policy_id,
            asset_selector={
                "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
                "operator": "=",
                "operandRight": edc_asset.asset_id,
            },
        )
        await client.create_contract_definition(contract_def)

        logger.info(
            "edc_publish_success",
            dpp_id=str(dpp.id),
            asset_id=edc_asset.asset_id,
            contract_id=contract_id,
        )

        return PublishResult(
            status="success",
            asset_id=edc_asset.asset_id,
            access_policy_id=access_policy_id,
            usage_policy_id=usage_policy_id,
            contract_definition_id=contract_id,
        )
