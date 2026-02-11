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

_DEFAULT_SCOPE_MULTIPLIERS: dict[str, float] = {
    "cradle-to-gate": 1.0,
    "gate-to-gate": 0.3,
    "cradle-to-grave": 1.2,
}

_DEFAULT_METHODOLOGY = "activity-based-gwp"
_DEFAULT_DISCLOSURE = (
    "Calculated estimate for interoperability and comparison; "
    "not a certification substitute."
)


class PCFEngine:
    """Stateless Product Carbon Footprint calculator.

    Usage::

        engine = PCFEngine(FactorDatabase())
        result = engine.calculate(inventory, scope="cradle-to-gate")
    """

    def __init__(
        self,
        factor_db: FactorDatabase,
        *,
        scope_multipliers: dict[str, float] | None = None,
        methodology: str = _DEFAULT_METHODOLOGY,
        methodology_disclosure: str = _DEFAULT_DISCLOSURE,
    ) -> None:
        self._factor_db = factor_db
        self._scope_multipliers = scope_multipliers or dict(_DEFAULT_SCOPE_MULTIPLIERS)
        self._methodology = methodology
        self._methodology_disclosure = methodology_disclosure

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
        breakdown = self._apply_scope_boundary(scope, breakdown, self._scope_multipliers)

        total_gwp = sum(b.gwp_kg_co2e for b in breakdown)

        return PCFResult(
            total_gwp_kg_co2e=round(total_gwp, 6),
            breakdown=breakdown,
            scope=scope,
            methodology=self._methodology,
            methodology_disclosure=self._methodology_disclosure,
        )

    @staticmethod
    def _apply_scope_boundary(
        scope: str,
        breakdown: list[MaterialBreakdown],
        scope_multipliers: dict[str, float],
    ) -> list[MaterialBreakdown]:
        """Apply scope-boundary multiplier to each breakdown entry.

        This is a placeholder implementation — the user will refine
        the multipliers for more accurate life-cycle modelling.
        """
        if scope not in scope_multipliers:
            raise ValueError(
                f"Unknown LCA scope '{scope}'. "
                f"Valid scopes: {', '.join(sorted(scope_multipliers))}"
            )
        multiplier = scope_multipliers[scope]
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
