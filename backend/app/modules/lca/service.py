"""LCA service — business logic layer for PCF calculations.

Wraps the stateless ``PCFEngine`` with DPP-aware operations:
retrieving the AAS environment from a DPP revision, persisting
calculation results, and comparing revisions.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import DPP, DPPRevision, LCACalculation
from app.modules.lca.engine import PCFEngine
from app.modules.lca.extractor import extract_material_inventory
from app.modules.lca.factors.loader import FactorDatabase
from app.modules.lca.schemas import (
    ComparisonReport,
    LCAReport,
    MaterialBreakdown,
    MaterialInventory,
)

logger = get_logger(__name__)

# Module-level singleton engine (loaded once, reused across requests)
_engine: PCFEngine | None = None


def _get_engine() -> PCFEngine:
    """Return the module-level PCFEngine singleton."""
    global _engine  # noqa: PLW0603
    if _engine is None:
        settings = get_settings()
        db_path = settings.lca_factor_database_path or None
        factor_db = FactorDatabase(yaml_path=db_path)
        _engine = PCFEngine(factor_db)
    return _engine


class LCAService:
    """DPP-aware LCA / PCF calculation service.

    Usage::

        service = LCAService(db_session)
        report = await service.calculate_dpp_pcf(dpp_id, tenant_id, created_by="sub")
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._engine = _get_engine()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def calculate_dpp_pcf(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
        scope: str | None = None,
        created_by: str = "",
    ) -> LCAReport:
        """Calculate the PCF for a DPP's latest revision.

        Retrieves the AAS environment, extracts the material inventory,
        runs the PCF engine, and persists the result.

        Args:
            dpp_id: The DPP to calculate PCF for.
            tenant_id: Tenant scope for the DPP lookup.
            scope: LCA scope boundary override. If ``None``, uses config default.
            created_by: Subject ID of the requesting user.

        Returns:
            An ``LCAReport`` with the full calculation results.

        Raises:
            ValueError: If the DPP or its revision cannot be found.
        """
        settings = get_settings()
        resolved_scope = scope or settings.lca_default_scope

        aas_env, revision_no = await self._get_aas_env(dpp_id, tenant_id)

        inventory = extract_material_inventory(aas_env)
        result = self._engine.calculate(inventory, scope=resolved_scope)

        # Persist calculation
        calc = LCACalculation(
            dpp_id=dpp_id,
            tenant_id=tenant_id,
            revision_no=revision_no,
            methodology=result.methodology,
            scope=result.scope,
            total_gwp_kg_co2e=result.total_gwp_kg_co2e,
            impact_categories={"gwp": result.total_gwp_kg_co2e},
            material_inventory=inventory.model_dump(),
            factor_database_version=self._engine.factor_database_version,
            report_json={
                "breakdown": [b.model_dump() for b in result.breakdown],
            },
            created_by_subject=created_by,
        )
        self._session.add(calc)
        await self._session.flush()

        logger.info(
            "lca_calculation_completed",
            dpp_id=str(dpp_id),
            revision_no=revision_no,
            scope=resolved_scope,
            total_gwp=result.total_gwp_kg_co2e,
            materials=len(inventory.items),
        )

        return self._to_report(calc, result.breakdown, inventory)

    async def get_latest_report(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
    ) -> LCAReport | None:
        """Return the most recent LCA report for a DPP, or ``None``."""
        result = await self._session.execute(
            select(LCACalculation)
            .where(
                LCACalculation.dpp_id == dpp_id,
                LCACalculation.tenant_id == tenant_id,
            )
            .order_by(LCACalculation.created_at.desc())
            .limit(1)
        )
        calc = result.scalar_one_or_none()
        if calc is None:
            return None

        return self._calc_to_report(calc)

    async def compare_revisions(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
        rev_a: int,
        rev_b: int,
    ) -> ComparisonReport:
        """Compare PCF calculations between two DPP revisions.

        Raises:
            ValueError: If either revision's calculation is not found.
        """
        report_a = await self._get_report_for_revision(dpp_id, tenant_id, rev_a)
        report_b = await self._get_report_for_revision(dpp_id, tenant_id, rev_b)

        delta = report_b.total_gwp_kg_co2e - report_a.total_gwp_kg_co2e
        delta_pct: float | None = None
        if report_a.total_gwp_kg_co2e > 0:
            delta_pct = round((delta / report_a.total_gwp_kg_co2e) * 100, 2)

        return ComparisonReport(
            dpp_id=dpp_id,
            revision_a=rev_a,
            revision_b=rev_b,
            report_a=report_a,
            report_b=report_b,
            delta_gwp_kg_co2e=round(delta, 6),
            delta_percentage=delta_pct,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_aas_env(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
    ) -> tuple[dict[str, Any], int]:
        """Retrieve the latest AAS environment and revision number."""
        dpp_result = await self._session.execute(
            select(DPP).where(
                DPP.id == dpp_id,
                DPP.tenant_id == tenant_id,
            )
        )
        dpp = dpp_result.scalar_one_or_none()
        if dpp is None:
            raise ValueError(f"DPP {dpp_id} not found")

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
        return aas_env, revision.revision_no

    async def _get_report_for_revision(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
        revision_no: int,
    ) -> LCAReport:
        """Get the LCA report for a specific DPP revision."""
        result = await self._session.execute(
            select(LCACalculation).where(
                LCACalculation.dpp_id == dpp_id,
                LCACalculation.tenant_id == tenant_id,
                LCACalculation.revision_no == revision_no,
            )
        )
        calc = result.scalar_one_or_none()
        if calc is None:
            raise ValueError(f"No LCA calculation found for DPP {dpp_id} revision {revision_no}")

        return self._calc_to_report(calc)

    @staticmethod
    def _to_report(
        calc: LCACalculation,
        breakdown: list[MaterialBreakdown],
        inventory: MaterialInventory,
    ) -> LCAReport:
        """Build an LCAReport from a freshly persisted calculation."""
        return LCAReport(
            id=calc.id,
            dpp_id=calc.dpp_id,
            revision_no=calc.revision_no,
            methodology=calc.methodology,
            scope=calc.scope,
            total_gwp_kg_co2e=calc.total_gwp_kg_co2e,
            impact_categories=calc.impact_categories,
            material_inventory=inventory,
            factor_database_version=calc.factor_database_version,
            created_at=calc.created_at,
            breakdown=breakdown,
        )

    @staticmethod
    def _calc_to_report(calc: LCACalculation) -> LCAReport:
        """Build an LCAReport from a persisted LCACalculation row."""
        # Reconstruct breakdown from stored report_json
        raw_breakdown = calc.report_json.get("breakdown", [])
        breakdown = [MaterialBreakdown(**b) for b in raw_breakdown]

        # Reconstruct inventory from stored material_inventory
        inventory = MaterialInventory(**calc.material_inventory)

        return LCAReport(
            id=calc.id,
            dpp_id=calc.dpp_id,
            revision_no=calc.revision_no,
            methodology=calc.methodology,
            scope=calc.scope,
            total_gwp_kg_co2e=calc.total_gwp_kg_co2e,
            impact_categories=calc.impact_categories,
            material_inventory=inventory,
            factor_database_version=calc.factor_database_version,
            created_at=calc.created_at,
            breakdown=breakdown,
        )
