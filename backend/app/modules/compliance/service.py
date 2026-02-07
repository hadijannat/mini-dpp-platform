"""Compliance service — business logic layer for ESPR compliance checks.

Wraps the stateless ``ComplianceEngine`` with DPP-aware operations:
retrieving the AAS environment from a DPP revision, persisting compliance
reports, and providing the pre-publish gate (Contract C).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import DPP, DPPRevision
from app.modules.compliance.engine import ComplianceEngine
from app.modules.compliance.schemas import ComplianceReport

logger = get_logger(__name__)

# Module-level singleton engine (loaded once, reused across requests)
_engine: ComplianceEngine | None = None


def _get_engine() -> ComplianceEngine:
    """Return the module-level ComplianceEngine singleton."""
    global _engine  # noqa: PLW0603
    if _engine is None:
        _engine = ComplianceEngine()
    return _engine


class ComplianceService:
    """DPP-aware compliance checking service.

    Usage::

        service = ComplianceService(db_session)
        report = await service.check_dpp(dpp_id, tenant_id)
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._engine = _get_engine()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_dpp(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
        category: str | None = None,
    ) -> ComplianceReport:
        """Run a compliance check on a DPP's latest revision.

        Retrieves the AAS environment from the DPP's latest revision,
        evaluates it against the applicable rule set, and returns the
        compliance report with the ``dpp_id`` attached.

        Args:
            dpp_id: The DPP to check.
            tenant_id: Tenant scope for the DPP lookup.
            category: Explicit product category override. If ``None``,
                the engine will auto-detect the category from semantic IDs.

        Returns:
            A :class:`ComplianceReport` with violations and summary.

        Raises:
            ValueError: If the DPP or its revision cannot be found.
        """
        aas_env = await self._get_aas_env(dpp_id, tenant_id)

        report = self._engine.evaluate(aas_env, category=category)
        report.dpp_id = dpp_id

        logger.info(
            "compliance_check_completed",
            dpp_id=str(dpp_id),
            category=report.category,
            is_compliant=report.is_compliant,
            violations=report.summary.critical_violations,
        )

        return report

    async def check_pre_publish(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
    ) -> ComplianceReport:
        """Pre-publish compliance gate (Contract C).

        Called by ``DPPService.publish_dpp()`` when the
        ``compliance_check_on_publish`` setting is enabled. Critical
        violations block the publish operation.

        Returns:
            A :class:`ComplianceReport`. The caller should inspect
            ``report.is_compliant`` to decide whether to proceed.

        Raises:
            ValueError: If the DPP or its revision cannot be found.
        """
        report = await self.check_dpp(dpp_id, tenant_id)

        if not report.is_compliant:
            logger.warning(
                "publish_blocked_by_compliance",
                dpp_id=str(dpp_id),
                category=report.category,
                critical_violations=report.summary.critical_violations,
            )

        return report

    async def check_aas_env(
        self,
        aas_env: dict[str, Any],
        category: str | None = None,
    ) -> ComplianceReport:
        """Run a compliance check on a raw AAS environment dict.

        Useful for checking compliance before creating a DPP (e.g. import
        validation). No database lookup is performed.
        """
        return self._engine.evaluate(aas_env, category=category)

    def get_engine(self) -> ComplianceEngine:
        """Expose the underlying engine for rule listing."""
        return self._engine

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_aas_env(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Retrieve the latest AAS environment for a DPP."""
        # Verify the DPP exists and belongs to the tenant
        dpp_result = await self._session.execute(
            select(DPP).where(
                DPP.id == dpp_id,
                DPP.tenant_id == tenant_id,
            )
        )
        dpp = dpp_result.scalar_one_or_none()
        if dpp is None:
            raise ValueError(f"DPP {dpp_id} not found")

        # Get latest revision
        revision_result = await self._session.execute(
            select(DPPRevision)
            .where(
                DPPRevision.dpp_id == dpp_id,
                DPPRevision.tenant_id == tenant_id,
            )
            .order_by(DPPRevision.revision_no.desc())
            .limit(1)
        )
        revision = revision_result.scalar_one_or_none()
        if revision is None:
            raise ValueError(f"No revision found for DPP {dpp_id}")

        aas_env: dict[str, Any] = revision.aas_env_json
        return aas_env
