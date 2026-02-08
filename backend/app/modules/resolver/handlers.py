"""Fire-and-forget handler for auto-registering resolver links on DPP publish.

Mirrors the pattern in ``epcis.handlers``.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def auto_register_resolver_links(
    session: AsyncSession,
    dpp: Any,
    tenant_id: UUID,
    created_by: str,
) -> None:
    """Register resolver links after DPP publish (fire-and-forget).

    Checks ``resolver_enabled`` and ``resolver_auto_register`` settings.
    Uses a savepoint so failures do not roll back the parent transaction.
    """
    settings = get_settings()
    if not settings.resolver_enabled or not settings.resolver_auto_register:
        return

    base_url = settings.resolver_base_url
    if not base_url:
        # Fall back to first CORS origin (common dev pattern)
        base_url = settings.cors_origins[0] if settings.cors_origins else "http://localhost:8000"

    try:
        async with session.begin_nested():
            from app.modules.resolver.service import ResolverService

            service = ResolverService(session)
            await service.auto_register_for_dpp(
                dpp=dpp,
                tenant_id=tenant_id,
                created_by=created_by,
                base_url=base_url,
            )
    except Exception:
        logger.warning(
            "resolver_auto_register_failed",
            dpp_id=str(dpp.id),
            exc_info=True,
        )
