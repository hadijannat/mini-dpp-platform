"""Agent lifecycle — poll loop with graceful shutdown."""

from __future__ import annotations

import asyncio
import logging
import signal

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_shutdown: asyncio.Event = asyncio.Event()


def _handle_signal() -> None:
    """Signal handler that triggers graceful shutdown."""
    logger.info("Shutdown signal received")
    _shutdown.set()


async def run_agent(*, max_cycles: int = 0) -> None:
    """Run the OPC UA agent poll loop.

    Args:
        max_cycles: If >0, exit after this many iterations (for testing).
                    If 0, run until shutdown signal.
    """
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

    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, _handle_signal)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass

        _shutdown.clear()
        cycle = 0
        poll_interval = settings.opcua_agent_poll_interval_seconds

        logger.info("OPC UA agent started — poll interval %ds", poll_interval)

        while not _shutdown.is_set():
            cycle += 1
            logger.debug("Agent cycle %d", cycle)

            # TODO: poll mappings and process subscriptions

            if max_cycles > 0 and cycle >= max_cycles:
                logger.info("Reached max_cycles=%d — exiting", max_cycles)
                break

            await asyncio.sleep(poll_interval)

    finally:
        await engine.dispose()
        logger.info("OPC UA agent engine disposed")
