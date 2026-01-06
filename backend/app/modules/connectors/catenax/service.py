"""
Catena-X Connector Service.
Orchestrates DTR registration and optional EDC DSP metadata inclusion.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Connector, ConnectorStatus, ConnectorType
from app.modules.connectors.catenax.dtr_client import DTRClient, DTRConfig
from app.modules.connectors.catenax.mapping import build_shell_descriptor
from app.modules.dpps.service import DPPService

logger = get_logger(__name__)


class CatenaXConnectorService:
    """
    Service for managing Catena-X DTR publishing with optional EDC DSP metadata.

    Provides connector lifecycle management and DPP publishing
    to Catena-X dataspaces.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._dpp_service = DPPService(session)

    async def get_connector(self, connector_id: UUID) -> Connector | None:
        """Get a connector by ID."""
        result = await self._session.execute(select(Connector).where(Connector.id == connector_id))
        return result.scalar_one_or_none()

    async def get_connectors(
        self,
        connector_type: ConnectorType | None = None,
    ) -> list[Connector]:
        """Get all connectors, optionally filtered by type."""
        query = select(Connector).order_by(Connector.created_at.desc())

        if connector_type:
            query = query.where(Connector.connector_type == connector_type)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def create_connector(
        self,
        name: str,
        config: dict[str, Any],
        created_by_subject: str,
    ) -> Connector:
        """
        Create a new Catena-X connector.

        Config should include:
        - dtr_base_url: DTR API base URL
        - auth_type: "oidc" or "token"
        - client_id, client_secret (for OIDC)
        - token (for token auth)
        - bpn: Business Partner Number
        - submodel_base_url: URL where submodels are exposed
        - edc_dsp_endpoint: Optional EDC DSP endpoint
        """
        connector = Connector(
            name=name,
            connector_type=ConnectorType.CATENA_X,
            config=config,
            status=ConnectorStatus.DISABLED,
            created_by_subject=created_by_subject,
        )

        self._session.add(connector)
        await self._session.flush()

        logger.info(
            "connector_created",
            connector_id=str(connector.id),
            name=name,
        )

        return connector

    async def test_connector(self, connector_id: UUID) -> dict[str, Any]:
        """
        Test connectivity for a Catena-X connector.

        Verifies DTR connectivity; EDC DSP endpoint is included as metadata only.
        and authentication is valid.
        """
        connector = await self.get_connector(connector_id)
        if not connector:
            return {"status": "error", "error_message": "Connector not found"}

        config = connector.config

        # Build DTR config
        dtr_config = DTRConfig(
            base_url=config.get("dtr_base_url", ""),
            auth_type=config.get("auth_type", "token"),
            client_id=config.get("client_id"),
            client_secret=config.get("client_secret"),
            token=config.get("token"),
            bpn=config.get("bpn"),
        )

        client = DTRClient(dtr_config)

        try:
            result = await client.test_connection()

            # Update connector status
            connector.last_tested_at = datetime.now(UTC)
            connector.last_test_result = result

            if result.get("status") == "connected":
                connector.status = ConnectorStatus.ACTIVE
            else:
                connector.status = ConnectorStatus.ERROR

            await self._session.flush()

            return result

        finally:
            await client.close()

    async def publish_dpp_to_dtr(
        self,
        connector_id: UUID,
        dpp_id: UUID,
    ) -> dict[str, Any]:
        """
        Publish a DPP to Catena-X DTR.

        Registers the shell descriptor with all submodel descriptors
        in the configured Digital Twin Registry.
        """
        connector = await self.get_connector(connector_id)
        if not connector:
            raise ValueError(f"Connector {connector_id} not found")

        if connector.status != ConnectorStatus.ACTIVE:
            raise ValueError(f"Connector {connector_id} is not active")

        dpp = await self._dpp_service.get_dpp(dpp_id)
        if not dpp:
            raise ValueError(f"DPP {dpp_id} not found")

        revision = await self._dpp_service.get_published_revision(dpp_id)
        if not revision:
            raise ValueError(f"DPP {dpp_id} has no published revision")

        config = connector.config

        # Build shell descriptor
        descriptor = build_shell_descriptor(
            dpp=dpp,
            revision=revision,
            submodel_base_url=config.get("submodel_base_url", ""),
            edc_dsp_endpoint=config.get("edc_dsp_endpoint"),
        )

        # Build DTR client
        dtr_config = DTRConfig(
            base_url=config.get("dtr_base_url", ""),
            auth_type=config.get("auth_type", "token"),
            client_id=config.get("client_id"),
            client_secret=config.get("client_secret"),
            token=config.get("token"),
            bpn=config.get("bpn"),
        )

        client = DTRClient(dtr_config)

        try:
            # Check if shell already exists
            existing = await client.get_shell(descriptor.id)

            if existing:
                # Update existing
                result = await client.update_shell(descriptor.id, descriptor)
                action = "updated"
            else:
                # Register new
                result = await client.register_shell(descriptor)
                action = "registered"

            logger.info(
                "dpp_published_to_dtr",
                dpp_id=str(dpp_id),
                connector_id=str(connector_id),
                shell_id=descriptor.id,
                action=action,
            )

            return {
                "status": "success",
                "action": action,
                "shell_id": descriptor.id,
                "dtr_response": result,
            }

        finally:
            await client.close()
