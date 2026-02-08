"""Fire-and-forget handler for auto-registering shell descriptors on DPP publish.

Mirrors the pattern in ``resolver.handlers``.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def auto_register_shell_descriptor(
    session: AsyncSession,
    dpp: Any,
    revision: Any,
    tenant_id: UUID,
    created_by: str,
) -> None:
    """Register shell descriptor + discovery mappings after DPP publish.

    Checks ``registry_enabled`` and ``registry_auto_register`` settings.
    Uses a savepoint so failures do not roll back the parent transaction.
    """
    settings = get_settings()
    if not settings.registry_enabled or not settings.registry_auto_register:
        return

    submodel_base_url = (
        settings.cors_origins[0] if settings.cors_origins else "http://localhost:8000"
    )

    try:
        async with session.begin_nested():
            from app.modules.registry.service import BuiltInRegistryService

            service = BuiltInRegistryService(session)
            await service.auto_register_from_dpp(
                dpp=dpp,
                revision=revision,
                tenant_id=tenant_id,
                created_by=created_by,
                submodel_base_url=submodel_base_url,
            )
    except Exception:
        logger.warning(
            "registry_auto_register_failed",
            dpp_id=str(dpp.id),
            exc_info=True,
        )
