"""OPC UA connection lifecycle manager."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from asyncua import Client

logger = logging.getLogger("opcua_agent.connections")


@dataclass(slots=True)
class _ConnectionEntry:
    """Tracks a single OPC UA client connection."""

    source_id: UUID
    tenant_id: UUID
    endpoint_url: str
    client: Client
    backoff_seconds: float = 1.0


class ConnectionManager:
    """Manages OPC UA client connections with per-tenant limits.

    Each tenant can have at most ``max_per_tenant`` concurrent connections.
    Connections are keyed by ``source_id`` and can be reused across
    subscription setups.
    """

    MAX_BACKOFF = 120.0

    def __init__(self, *, max_per_tenant: int = 5) -> None:
        self._max_per_tenant = max_per_tenant
        self._connections: dict[UUID, _ConnectionEntry] = {}

    def connection_count(self, tenant_id: UUID) -> int:
        """Return the number of active connections for a tenant."""
        return sum(1 for e in self._connections.values() if e.tenant_id == tenant_id)

    async def connect(
        self,
        *,
        source_id: UUID,
        tenant_id: UUID,
        endpoint_url: str,
        security_policy: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> Client:
        """Connect to an OPC UA endpoint or return an existing connection.

        Raises ``ValueError`` if the tenant connection limit is reached.
        """
        # Return existing connection if present
        existing = self._connections.get(source_id)
        if existing is not None:
            return existing.client

        # Check tenant limit
        if self.connection_count(tenant_id) >= self._max_per_tenant:
            raise ValueError(
                f"Tenant {tenant_id} has reached the connection limit of {self._max_per_tenant}"
            )

        client = Client(url=endpoint_url)

        if username and password:
            client.set_user(username)
            client.set_password(password)

        if security_policy:
            await client.set_security_string(security_policy)

        await client.connect()

        entry = _ConnectionEntry(
            source_id=source_id,
            tenant_id=tenant_id,
            endpoint_url=endpoint_url,
            client=client,
        )
        self._connections[source_id] = entry
        logger.info(
            "Connected to %s (source=%s, tenant=%s)",
            endpoint_url,
            source_id,
            tenant_id,
        )
        return client

    async def disconnect(self, source_id: UUID) -> None:
        """Disconnect and remove a connection by source_id."""
        entry = self._connections.pop(source_id, None)
        if entry is None:
            return
        try:
            await entry.client.disconnect()
            logger.info("Disconnected source %s from %s", source_id, entry.endpoint_url)
        except Exception:
            logger.exception(
                "Error disconnecting source %s from %s",
                source_id,
                entry.endpoint_url,
            )

    async def disconnect_all(self) -> None:
        """Disconnect all active connections."""
        source_ids = list(self._connections.keys())
        for source_id in source_ids:
            await self.disconnect(source_id)

    def get_client(self, source_id: UUID) -> Client | None:
        """Return the OPC UA client for a source, or None if not connected."""
        entry = self._connections.get(source_id)
        return entry.client if entry is not None else None

    def connected_source_ids(self) -> set[UUID]:
        """Return source IDs with active connections."""
        return set(self._connections.keys())
