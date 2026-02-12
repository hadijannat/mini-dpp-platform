"""
Catena-X Connector Service.
Orchestrates DTR registration and optional EDC DSP metadata inclusion.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.encryption import ConnectorConfigEncryptor, EncryptionError
from app.core.logging import get_logger
from app.db.models import (
    Connector,
    ConnectorStatus,
    ConnectorType,
    ResourceShare,
    VisibilityScope,
)
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
        self._encryptor: ConnectorConfigEncryptor | None = None
        settings = get_settings()
        if settings.encryption_master_key:
            self._encryptor = ConnectorConfigEncryptor(settings.encryption_master_key)

    async def get_connector(self, connector_id: UUID, tenant_id: UUID) -> Connector | None:
        """Get a connector by ID."""
        result = await self._session.execute(
            select(Connector).where(
                Connector.id == connector_id,
                Connector.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_connectors(
        self,
        tenant_id: UUID,
        connector_type: ConnectorType | None = None,
    ) -> list[Connector]:
        """Get all connectors, optionally filtered by type."""
        query = (
            select(Connector)
            .where(Connector.tenant_id == tenant_id)
            .order_by(Connector.created_at.desc())
        )

        if connector_type:
            query = query.where(Connector.connector_type == connector_type)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_shared_connector_ids(
        self,
        *,
        tenant_id: UUID,
        user_subject: str,
    ) -> set[UUID]:
        """Get active connector shares for a subject."""
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(ResourceShare.resource_id).where(
                ResourceShare.tenant_id == tenant_id,
                ResourceShare.resource_type == "connector",
                ResourceShare.user_subject == user_subject,
                or_(
                    ResourceShare.expires_at.is_(None),
                    ResourceShare.expires_at > now,
                ),
            )
        )
        return set(result.scalars().all())

    async def is_connector_shared_with_user(
        self,
        *,
        tenant_id: UUID,
        connector_id: UUID,
        user_subject: str,
    ) -> bool:
        """Check whether connector is shared with user."""
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(ResourceShare.id).where(
                ResourceShare.tenant_id == tenant_id,
                ResourceShare.resource_type == "connector",
                ResourceShare.resource_id == connector_id,
                ResourceShare.user_subject == user_subject,
                or_(
                    ResourceShare.expires_at.is_(None),
                    ResourceShare.expires_at > now,
                ),
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_connectors_for_subject(
        self,
        *,
        tenant_id: UUID,
        user_subject: str,
        is_tenant_admin: bool,
        scope: str = "mine",
        connector_type: ConnectorType | None = None,
    ) -> tuple[list[Connector], set[UUID]]:
        """
        Get connectors visible to current subject with SQL prefiltering.

        Scope values:
        - mine: connectors created by caller
        - shared: connectors explicitly shared with caller
        - all: all accessible (tenant admin sees all tenant connectors)
        """
        query = select(Connector).where(Connector.tenant_id == tenant_id)
        if connector_type:
            query = query.where(Connector.connector_type == connector_type)

        shared_ids = await self.get_shared_connector_ids(
            tenant_id=tenant_id,
            user_subject=user_subject,
        )

        if is_tenant_admin:
            if scope == "mine":
                query = query.where(Connector.created_by_subject == user_subject)
            elif scope == "shared":
                if shared_ids:
                    query = query.where(
                        Connector.id.in_(shared_ids),
                        Connector.created_by_subject != user_subject,
                    )
                else:
                    query = query.where(false())
        else:
            if scope == "mine":
                query = query.where(Connector.created_by_subject == user_subject)
            elif scope == "shared":
                if shared_ids:
                    query = query.where(
                        Connector.id.in_(shared_ids),
                        Connector.created_by_subject != user_subject,
                    )
                else:
                    query = query.where(false())
            else:
                access_conditions = [
                    Connector.created_by_subject == user_subject,
                    Connector.visibility_scope == VisibilityScope.TENANT,
                ]
                if shared_ids:
                    access_conditions.append(Connector.id.in_(shared_ids))
                query = query.where(or_(*access_conditions))

        result = await self._session.execute(query.order_by(Connector.created_at.desc()))
        return list(result.scalars().all()), shared_ids

    async def create_connector(
        self,
        tenant_id: UUID,
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
        encrypted_config = self._encrypt_config(config)
        connector = Connector(
            tenant_id=tenant_id,
            name=name,
            connector_type=ConnectorType.CATENA_X,
            config=encrypted_config,
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

    async def test_connector(self, connector_id: UUID, tenant_id: UUID) -> dict[str, Any]:
        """
        Test connectivity for a Catena-X connector.

        Verifies DTR connectivity; EDC DSP endpoint is included as metadata only.
        and authentication is valid.
        """
        connector = await self.get_connector(connector_id, tenant_id)
        if not connector:
            return {"status": "error", "error_message": "Connector not found"}

        config = self._decrypt_config(connector.config)

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
        except ValueError as exc:
            result = {"status": "error", "error_message": str(exc)}
        finally:
            await client.close()

        # Update connector status
        connector.last_tested_at = datetime.now(UTC)
        connector.last_test_result = result

        if result.get("status") == "connected":
            connector.status = ConnectorStatus.ACTIVE
        else:
            connector.status = ConnectorStatus.ERROR

        await self._session.flush()

        return result

    async def publish_dpp_to_dtr(
        self,
        connector_id: UUID,
        dpp_id: UUID,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """
        Publish a DPP to Catena-X DTR.

        Registers the shell descriptor with all submodel descriptors
        in the configured Digital Twin Registry.
        """
        connector = await self.get_connector(connector_id, tenant_id)
        if not connector:
            raise ValueError(f"Connector {connector_id} not found")

        if connector.status != ConnectorStatus.ACTIVE:
            raise ValueError(f"Connector {connector_id} is not active")

        dpp = await self._dpp_service.get_dpp(dpp_id, tenant_id)
        if not dpp:
            raise ValueError(f"DPP {dpp_id} not found")

        revision = await self._dpp_service.get_published_revision(dpp_id, tenant_id)
        if not revision:
            raise ValueError(f"DPP {dpp_id} has no published revision")

        config = self._decrypt_config(connector.config)

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

    def _encrypt_config(self, config: dict[str, Any]) -> dict[str, Any]:
        if self._encryptor is None:
            if config.get("token") or config.get("client_secret"):
                raise ValueError(
                    "encryption_master_key must be configured before storing connector secrets"
                )
            return config
        try:
            return self._encryptor.encrypt_config(config)
        except EncryptionError as exc:
            raise ValueError(str(exc)) from exc

    def _decrypt_config(self, config: dict[str, Any]) -> dict[str, Any]:
        if self._encryptor is None:
            return config
        try:
            return self._encryptor.decrypt_config(config)
        except EncryptionError as exc:
            raise ValueError(str(exc)) from exc
