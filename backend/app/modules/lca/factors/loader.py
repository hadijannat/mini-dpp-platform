"""YAML-based emission factor database loader.

Loads material emission factors from a YAML file and provides lookup
methods for the PCF calculation engine.
"""

from __future__ import annotations

from importlib import resources as importlib_resources
from pathlib import Path

import yaml

from app.core.logging import get_logger
from app.modules.lca.schemas import EmissionFactor

logger = get_logger(__name__)


class FactorDatabase:
    """Emission factor database loaded from YAML.

    Usage::

        db = FactorDatabase()
        factor = db.get_factor("steel")
        factor = db.find_best_factor("Stainless Steel Alloy")
    """

    def __init__(self, yaml_path: str | Path | None = None) -> None:
        self._factors: dict[str, EmissionFactor] = {}
        self._version: str = "0.0"
        self._load(yaml_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def version(self) -> str:
        """Return the version string from the loaded YAML."""
        return self._version

    def get_factor(self, material: str) -> EmissionFactor | None:
        """Exact-match lookup by normalised material name."""
        return self._factors.get(material.lower().strip())

    def find_best_factor(self, material_name: str) -> EmissionFactor | None:
        """Fuzzy lookup: normalise, then check exact match and substring.

        Returns the first factor whose key is contained in the query or
        vice-versa. Falls back to ``None`` if nothing matches.
        """
        normalised = material_name.lower().strip().replace(" ", "_")

        # Exact match first
        exact = self._factors.get(normalised)
        if exact is not None:
            return exact

        # Substring match: factor key in query or query in factor key
        for key, factor in self._factors.items():
            if key in normalised or normalised in key:
                return factor

        return None

    def list_materials(self) -> list[str]:
        """Return all known material names (sorted)."""
        return sorted(self._factors.keys())

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self, yaml_path: str | Path | None = None) -> None:
        """Load factors from YAML file."""
        path = Path(yaml_path) if yaml_path is not None else self._default_path()

        if not path.is_file():
            logger.warning("factor_database_not_found", path=str(path))
            return

        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        if not isinstance(data, dict):
            logger.warning("invalid_factor_database", path=str(path))
            return

        self._version = data.get("version", "0.0")
        raw_factors = data.get("factors", [])
        if not isinstance(raw_factors, list):
            logger.warning("invalid_factors_list", path=str(path))
            return

        for raw in raw_factors:
            if not isinstance(raw, dict):
                continue
            material_key = str(raw.get("material", "")).lower().strip()
            if not material_key:
                continue
            try:
                self._factors[material_key] = EmissionFactor(
                    material=raw.get("material", ""),
                    category=raw.get("category", ""),
                    factor_kg_co2e_per_kg=float(raw.get("factor_kg_co2e_per_kg", 0.0)),
                    source=raw.get("source", ""),
                    scope=raw.get("scope", "cradle-to-gate"),
                    year=int(raw.get("year", 2023)),
                )
            except (ValueError, TypeError):
                logger.warning(
                    "skipping_invalid_emission_factor",
                    material=material_key,
                    exc_info=True,
                )

        logger.info(
            "factor_database_loaded",
            version=self._version,
            factor_count=len(self._factors),
            path=path.name,
        )

    @staticmethod
    def _default_path() -> Path:
        """Resolve the default materials.yaml bundled with this package."""
        pkg = importlib_resources.files("app.modules.lca.factors")
        return Path(str(pkg)) / "materials.yaml"
