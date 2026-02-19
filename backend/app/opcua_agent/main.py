"""Agent lifecycle — poll loop with graceful shutdown."""

from __future__ import annotations

import asyncio
import logging
import signal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.opcua_agent.connection_manager import ConnectionManager
from app.opcua_agent.flush_engine import flush_buffer
from app.opcua_agent.ingestion_buffer import IngestionBuffer

logger = logging.getLogger(__name__)

_shutdown: asyncio.Event | None = None


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
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    _shutdown.clear()
    poll_interval = settings.opcua_agent_poll_interval_seconds

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

            try:
                await asyncio.wait_for(
                    _shutdown.wait(),
                    timeout=poll_interval,
                )
            except asyncio.TimeoutError:
                pass
    finally:
        await conn_manager.disconnect_all()
        await engine.dispose()
        logger.info("OPC UA agent stopped after %d cycles", cycle)


async def _sync_subscriptions(
    session_factory: async_sessionmaker[AsyncSession],
    conn_manager: ConnectionManager,
    buffer: IngestionBuffer,
) -> None:
    """Poll DB for enabled mappings and sync OPC UA subscriptions.

    Full implementation connects to OPC UA servers and creates monitored
    items. For now, this is a no-op placeholder.
    """
    pass
