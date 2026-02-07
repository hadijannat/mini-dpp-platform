"""Stateless PCF (Product Carbon Footprint) calculation engine.

Computes GWP impact from a material inventory using emission factors
from the loaded factor database. Scope boundaries apply multipliers
to approximate different life-cycle stages.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.modules.lca.factors.loader import FactorDatabase
from app.modules.lca.schemas import (
    MaterialBreakdown,
    MaterialInventory,
    PCFResult,
)

logger = get_logger(__name__)

# Scope boundary multipliers (placeholder — user will refine)
_SCOPE_MULTIPLIERS: dict[str, float] = {
    "cradle-to-gate": 1.0,
    "gate-to-gate": 0.3,
    "cradle-to-grave": 1.2,
}

_DEFAULT_METHODOLOGY = "activity-based-gwp"


class PCFEngine:
    """Stateless Product Carbon Footprint calculator.

    Usage::

        engine = PCFEngine(FactorDatabase())
        result = engine.calculate(inventory, scope="cradle-to-gate")
    """

    def __init__(self, factor_db: FactorDatabase) -> None:
        self._factor_db = factor_db

    @property
    def factor_database_version(self) -> str:
        """Return the version of the underlying factor database."""
        return self._factor_db.version

    def calculate(
        self,
        inventory: MaterialInventory,
        scope: str = "cradle-to-gate",
    ) -> PCFResult:
        """Calculate the product carbon footprint for *inventory*.

        For each material item:
        - If ``pre_declared_pcf`` is set, use it directly as the total
          GWP for that item.
        - Otherwise, look up the emission factor and compute
          ``mass_kg * quantity * factor``.

        A scope-boundary multiplier is then applied.
        """
        breakdown: list[MaterialBreakdown] = []

        for item in inventory.items:
            if item.pre_declared_pcf is not None:
                gwp = item.pre_declared_pcf
                factor_used = 0.0
                source = "pre-declared"
            else:
                factor = self._factor_db.find_best_factor(item.material_name)
                if factor is None:
                    logger.warning(
                        "no_emission_factor",
                        material=item.material_name,
                    )
                    factor_used = 0.0
                    gwp = 0.0
                    source = "unknown"
                else:
                    factor_used = factor.factor_kg_co2e_per_kg
                    gwp = item.mass_kg * item.quantity * factor_used
                    source = factor.source

            breakdown.append(
                MaterialBreakdown(
                    material_name=item.material_name,
                    mass_kg=item.mass_kg,
                    factor_used=factor_used,
                    gwp_kg_co2e=gwp,
                    source=source,
                )
            )

        # Apply scope boundary
        breakdown = self._apply_scope_boundary(scope, breakdown)

        total_gwp = sum(b.gwp_kg_co2e for b in breakdown)

        return PCFResult(
            total_gwp_kg_co2e=round(total_gwp, 6),
            breakdown=breakdown,
            scope=scope,
            methodology=_DEFAULT_METHODOLOGY,
        )

    @staticmethod
    def _apply_scope_boundary(
        scope: str,
        breakdown: list[MaterialBreakdown],
    ) -> list[MaterialBreakdown]:
        """Apply scope-boundary multiplier to each breakdown entry.

        This is a placeholder implementation — the user will refine
        the multipliers for more accurate life-cycle modelling.
        """
        multiplier = _SCOPE_MULTIPLIERS.get(scope, 1.0)
        if multiplier == 1.0:
            return breakdown

        return [
            MaterialBreakdown(
                material_name=b.material_name,
                mass_kg=b.mass_kg,
                factor_used=b.factor_used,
                gwp_kg_co2e=round(b.gwp_kg_co2e * multiplier, 6),
                source=b.source,
            )
            for b in breakdown
        ]
