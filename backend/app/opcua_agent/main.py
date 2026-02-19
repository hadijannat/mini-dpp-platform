"""Agent lifecycle — poll loop with graceful shutdown."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from aiohttp import web
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.encryption import ConnectorConfigEncryptor
from app.db.models import OPCUAMapping, OPCUAMappingType, OPCUASource
from app.opcua_agent.connection_manager import ConnectionManager
from app.opcua_agent.flush_engine import flush_buffer
from app.opcua_agent.health import create_health_app
from app.opcua_agent.ingestion_buffer import IngestionBuffer
from app.opcua_agent.subscription_handler import DataChangeHandler

logger = logging.getLogger(__name__)

_shutdown: asyncio.Event | None = None


@dataclass(slots=True)
class _SubscriptionEntry:
    """Tracks one active asyncua subscription for an OPC UA mapping."""

    source_id: UUID
    subscription: Any
    handle: Any


_active_subscriptions: dict[UUID, _SubscriptionEntry] = {}


def _handle_signal() -> None:
    """Signal handler that triggers graceful shutdown."""
    logger.info("Shutdown signal received")
    if _shutdown is not None:
        _shutdown.set()


async def run_agent(*, max_cycles: int = 0) -> None:
    """Run the OPC UA agent poll loop.

    Args:
        max_cycles: If >0, exit after this many iterations (for testing).
                    If 0, run until shutdown signal.
    """
    global _shutdown  # noqa: PLW0603

    settings = get_settings()

    if not settings.opcua_enabled:
        logger.info("OPC UA ingestion disabled (opcua_enabled=False) — exiting")
        return

    engine = create_async_engine(
        str(settings.database_url),
        pool_size=5,
        max_overflow=2,
        pool_pre_ping=True,
        echo=settings.debug,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    buffer = IngestionBuffer()
    conn_manager = ConnectionManager(
        max_per_tenant=settings.opcua_max_connections_per_tenant,
    )

    _shutdown = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _handle_signal)

    _shutdown.clear()
    poll_interval = settings.opcua_agent_poll_interval_seconds

    # Start health server
    health_app = create_health_app()
    health_runner = web.AppRunner(health_app)
    await health_runner.setup()
    health_site = web.TCPSite(health_runner, "0.0.0.0", 8090)  # nosec B104
    await health_site.start()
    logger.info("Health server started on port 8090")

    logger.info("OPC UA agent started — poll interval %ds", poll_interval)

    cycle = 0
    try:
        while not _shutdown.is_set():
            cycle += 1

            # Phase 1: Poll for enabled mappings and sync subscriptions
            try:
                await _sync_subscriptions(session_factory, conn_manager, buffer)
            except Exception:
                logger.exception("Error syncing subscriptions")

            # Phase 2: Flush buffer to DPP revisions
            try:
                flushed = await flush_buffer(buffer, session_factory)
                if flushed > 0:
                    logger.info("Flushed %d DPP(s)", flushed)
            except Exception:
                logger.exception("Error flushing buffer")

            if max_cycles > 0 and cycle >= max_cycles:
                break

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    _shutdown.wait(),
                    timeout=poll_interval,
                )
    finally:
        await _clear_subscriptions()
        await health_runner.cleanup()
        await conn_manager.disconnect_all()
        await engine.dispose()
        logger.info("OPC UA agent stopped after %d cycles", cycle)


async def _sync_subscriptions(
    session_factory: async_sessionmaker[AsyncSession],
    conn_manager: ConnectionManager,
    buffer: IngestionBuffer,
) -> None:
    """Poll DB for enabled mappings and sync OPC UA subscriptions.

    Loads enabled AAS patch mappings, creates subscriptions for new mappings,
    and removes stale subscriptions that are no longer enabled.
    """
    settings = get_settings()
    desired = await _load_desired_mappings(session_factory)
    desired_ids = set(desired.keys())

    for mapping_id in list(_active_subscriptions.keys()):
        if mapping_id not in desired_ids:
            await _remove_subscription(mapping_id)

    for mapping_id, (mapping, source) in desired.items():
        if mapping_id in _active_subscriptions:
            continue

        password: str | None = None
        if source.username and source.password_encrypted:
            try:
                encryptor = ConnectorConfigEncryptor(settings.encryption_master_key)
                password = encryptor._decrypt_value(source.password_encrypted)
            except Exception:
                logger.exception(
                    "Failed to decrypt OPC UA source credentials",
                    extra={"source_id": str(source.id)},
                )
                continue

        try:
            client = await conn_manager.connect(
                source_id=source.id,
                tenant_id=source.tenant_id,
                endpoint_url=source.endpoint_url,
                security_policy=source.security_policy,
                username=source.username,
                password=password,
            )
        except Exception:
            logger.exception(
                "Failed to connect OPC UA source",
                extra={"source_id": str(source.id), "endpoint_url": source.endpoint_url},
            )
            continue

        try:
            assert mapping.dpp_id is not None
            assert mapping.target_submodel_id is not None
            assert mapping.target_aas_path is not None
            handler = DataChangeHandler(
                buffer=buffer,
                tenant_id=mapping.tenant_id,
                dpp_id=mapping.dpp_id,
                mapping_id=mapping.id,
                target_submodel_id=mapping.target_submodel_id,
                target_aas_path=mapping.target_aas_path,
                transform_expr=mapping.value_transform_expr,
            )
            sampling_interval_ms = (
                mapping.sampling_interval_ms or settings.opcua_default_sampling_interval_ms
            )
            subscription = await client.create_subscription(sampling_interval_ms, handler)
            node = client.get_node(mapping.opcua_node_id)
            handle = await subscription.subscribe_data_change(node)
            _active_subscriptions[mapping.id] = _SubscriptionEntry(
                source_id=source.id,
                subscription=subscription,
                handle=handle,
            )
            logger.info(
                "Subscribed OPC UA mapping %s on source %s",
                mapping.id,
                source.id,
            )
        except Exception:
            logger.exception(
                "Failed to create OPC UA subscription",
                extra={"mapping_id": str(mapping.id), "source_id": str(source.id)},
            )
            continue

    active_source_ids = {entry.source_id for entry in _active_subscriptions.values()}
    for source_id in conn_manager.connected_source_ids() - active_source_ids:
        await conn_manager.disconnect(source_id)


async def _clear_subscriptions() -> None:
    """Best-effort shutdown of all active subscriptions."""
    for mapping_id in list(_active_subscriptions.keys()):
        await _remove_subscription(mapping_id)


async def _remove_subscription(mapping_id: UUID) -> None:
    """Remove one active subscription by mapping ID."""
    entry = _active_subscriptions.pop(mapping_id, None)
    if entry is None:
        return
    with contextlib.suppress(Exception):
        if entry.handle is not None:
            await entry.subscription.unsubscribe(entry.handle)
    with contextlib.suppress(Exception):
        await entry.subscription.delete()


async def _load_desired_mappings(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[UUID, tuple[OPCUAMapping, OPCUASource]]:
    """Load mappings that are eligible for live AAS patch subscriptions."""
    async with session_factory() as session:
        result = await session.execute(
            select(OPCUAMapping, OPCUASource)
            .join(OPCUASource, OPCUAMapping.source_id == OPCUASource.id)
            .where(
                OPCUAMapping.is_enabled.is_(True),
                OPCUAMapping.mapping_type == OPCUAMappingType.AAS_PATCH,
            )
        )
        rows = result.all()

    desired: dict[UUID, tuple[OPCUAMapping, OPCUASource]] = {}
    for mapping, source in rows:
        if mapping.dpp_id is None:
            continue
        if not mapping.target_submodel_id or not mapping.target_aas_path:
            continue
        desired[mapping.id] = (mapping, source)
    return desired
