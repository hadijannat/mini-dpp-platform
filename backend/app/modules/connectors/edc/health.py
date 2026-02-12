"""
EDC controlplane readiness probe.

Checks that the EDC instance is running and reachable via the
management API health endpoint.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.modules.connectors.edc.client import EDCManagementClient

logger = get_logger(__name__)


async def check_edc_health(client: EDCManagementClient) -> dict[str, Any]:
    """
    Probe the EDC controlplane health endpoint.

    Args:
        client: An initialised ``EDCManagementClient``.

    Returns:
        A dict with ``status`` ("ok" | "error") and optional
        ``edc_version`` or error details.
    """
    try:
        result = await client.check_health()

        if "error_message" in result:
            # Some EDC distributions expose `/api/check/health` on a different port
            # than the management API. If health probing returns 404, validate basic
            # management reachability via a benign asset read call instead.
            if result.get("error_code") == 404:
                try:
                    await client.get_asset("__healthcheck_missing_asset__")
                    logger.info("edc_health_check_fallback_ok")
                    return {
                        "status": "ok",
                        "edc_version": "unknown",
                        "components": [],
                    }
                except Exception as fallback_exc:  # pragma: no cover - defensive
                    logger.warning(
                        "edc_health_check_fallback_failed",
                        error=str(fallback_exc),
                    )
            logger.warning(
                "edc_health_check_failed",
                error=result.get("error_message"),
            )
            return {
                "status": "error",
                "error_message": result.get("error_message"),
                "error_code": result.get("error_code"),
            }

        logger.info("edc_health_check_ok")
        return {
            "status": "ok",
            "edc_version": result.get("version", "unknown"),
            "components": result.get("componentResults", []),
        }

    except Exception as exc:
        logger.error("edc_health_check_exception", error=str(exc))
        return {
            "status": "error",
            "error_message": str(exc),
        }
