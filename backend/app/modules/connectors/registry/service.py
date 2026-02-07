"""High-level registry service for DPP registration.

Orchestrates building shell descriptors from DPP data and registering
them via a ``RegistryClient`` implementation.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.db.models import DPP, DPPRevision
from app.modules.connectors.catenax.mapping import build_shell_descriptor
from app.modules.connectors.registry.base import RegistryClient

logger = get_logger(__name__)


class RegistryService:
    """High-level service for DPP shell descriptor management."""

    async def register_dpp(
        self,
        dpp: DPP,
        revision: DPPRevision,
        base_url: str,
        client: RegistryClient,
    ) -> dict[str, Any]:
        """Build a shell descriptor for a DPP and register it.

        Args:
            dpp: The DPP entity.
            revision: The DPP revision to use for descriptor content.
            base_url: Base URL where submodel endpoints are exposed.
            client: Registry client implementation.

        Returns:
            The registry response dict.
        """
        descriptor = build_shell_descriptor(dpp, revision, base_url)
        payload = descriptor.to_dtr_payload()

        logger.info(
            "registering_dpp_shell",
            dpp_id=str(dpp.id),
            shell_id=descriptor.id,
        )

        result = await client.register_shell(payload)

        logger.info(
            "dpp_shell_registered",
            dpp_id=str(dpp.id),
            shell_id=descriptor.id,
        )

        return result

    async def update_dpp(
        self,
        dpp: DPP,
        revision: DPPRevision,
        base_url: str,
        client: RegistryClient,
    ) -> dict[str, Any]:
        """Update an existing shell descriptor for a DPP.

        Args:
            dpp: The DPP entity.
            revision: The DPP revision to use for descriptor content.
            base_url: Base URL where submodel endpoints are exposed.
            client: Registry client implementation.

        Returns:
            The registry response dict.
        """
        descriptor = build_shell_descriptor(dpp, revision, base_url)
        shell_id = descriptor.id
        payload = descriptor.to_dtr_payload()

        logger.info(
            "updating_dpp_shell",
            dpp_id=str(dpp.id),
            shell_id=shell_id,
        )

        result = await client.update_shell(shell_id, payload)

        logger.info(
            "dpp_shell_updated",
            dpp_id=str(dpp.id),
            shell_id=shell_id,
        )

        return result
