"""Stateless YAML-driven ESPR compliance engine.

Loads rule definitions from YAML at startup and evaluates them against
AAS environment dicts using per-category validators.
"""

from __future__ import annotations

from importlib import resources as importlib_resources
from pathlib import Path
from typing import Any

import yaml

from app.core.logging import get_logger
from app.modules.compliance.categories import detect_category
from app.modules.compliance.schemas import (
    CategoryRuleset,
    ComplianceReport,
    ComplianceSummary,
    RuleCatalogEntry,
    RuleDefinition,
)
from app.modules.compliance.validators.base import CategoryValidator
from app.modules.compliance.validators.battery import BatteryValidator
from app.modules.compliance.validators.electronic import ElectronicValidator
from app.modules.compliance.validators.textile import TextileValidator

logger = get_logger(__name__)

# Registry of category validators
_VALIDATORS: dict[str, CategoryValidator] = {
    "battery": BatteryValidator(),
    "textile": TextileValidator(),
    "electronic": ElectronicValidator(),
}


class ComplianceEngine:
    """Stateless, YAML-driven compliance evaluator.

    Usage::

        engine = ComplianceEngine()
        report = engine.evaluate(aas_env, category="battery")
    """

    def __init__(self, rules_dir: str | Path | None = None) -> None:
        self._rulesets: dict[str, _LoadedRuleset] = {}
        self._load_rules(rules_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        aas_env: dict[str, Any],
        category: str | None = None,
    ) -> ComplianceReport:
        """Evaluate an AAS environment against the rules for *category*.

        If *category* is ``None``, auto-detection from semantic IDs is
        attempted. If no category can be determined, an empty report for
        the ``"unknown"`` category is returned.
        """
        resolved_category = category or detect_category(aas_env) or "unknown"

        ruleset = self._rulesets.get(resolved_category)
        if ruleset is None:
            logger.warning("no_ruleset_for_category", category=resolved_category)
            return ComplianceReport(
                category=resolved_category,
                is_compliant=True,
                violations=[],
                summary=ComplianceSummary(
                    total_rules=0, passed=0, critical_violations=0, warnings=0, info=0
                ),
            )

        validator = _VALIDATORS.get(resolved_category, CategoryValidator())
        violations = validator.validate(aas_env, ruleset.rules)

        critical = sum(1 for v in violations if v.severity == "critical")
        warnings = sum(1 for v in violations if v.severity == "warning")
        info = sum(1 for v in violations if v.severity == "info")
        total = len(ruleset.rules)
        passed = total - len(violations)

        return ComplianceReport(
            category=resolved_category,
            is_compliant=critical == 0,
            violations=violations,
            summary=ComplianceSummary(
                total_rules=total,
                passed=passed,
                critical_violations=critical,
                warnings=warnings,
                info=info,
            ),
        )

    def list_categories(self) -> list[str]:
        """Return all loaded category names."""
        return sorted(self._rulesets.keys())

    def get_category_ruleset(self, category: str) -> CategoryRuleset | None:
        """Return the public ruleset metadata for *category*."""
        ruleset = self._rulesets.get(category)
        if ruleset is None:
            return None
        return CategoryRuleset(
            category=ruleset.category,
            version=ruleset.version,
            description=ruleset.description,
            rules=[
                RuleCatalogEntry(
                    id=r.id,
                    field_path=r.field_path,
                    condition=r.condition,
                    severity=r.severity,
                    message=r.message,
                    semantic_id=r.semantic_id,
                )
                for r in ruleset.rules
            ],
        )

    def get_all_rules(self) -> dict[str, CategoryRuleset]:
        """Return all rulesets keyed by category."""
        result: dict[str, CategoryRuleset] = {}
        for cat in self.list_categories():
            rs = self.get_category_ruleset(cat)
            if rs is not None:
                result[cat] = rs
        return result

    # ------------------------------------------------------------------
    # Rule loading
    # ------------------------------------------------------------------

    def _load_rules(self, rules_dir: str | Path | None = None) -> None:
        """Load YAML rule files from the rules directory."""
        rules_path = Path(rules_dir) if rules_dir is not None else self._default_rules_path()

        if not rules_path.is_dir():
            logger.warning("rules_directory_not_found", path=str(rules_path))
            return

        for yaml_file in sorted(rules_path.glob("*.yaml")):
            try:
                self._load_rule_file(yaml_file)
            except Exception:
                logger.exception("rule_file_load_error", file=str(yaml_file))

    @staticmethod
    def _default_rules_path() -> Path:
        """Resolve the default rules/ directory relative to this package."""
        pkg = importlib_resources.files("app.modules.compliance")
        # importlib.resources returns a Traversable; for a real file-system
        # package this is a Path.
        return Path(str(pkg)) / "rules"

    def _load_rule_file(self, path: Path) -> None:
        """Parse a single YAML rule file and register it."""
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        if not isinstance(data, dict):
            logger.warning("invalid_rule_file", file=str(path))
            return

        category = data.get("category", "")
        version = data.get("version", "0.0")
        description = data.get("description", "")
        raw_rules = data.get("rules", [])
        if not isinstance(raw_rules, list):
            logger.warning("invalid_rules_list", file=str(path))
            return

        rules: list[RuleDefinition] = []
        for raw in raw_rules:
            if not isinstance(raw, dict):
                continue
            rules.append(
                RuleDefinition(
                    id=raw.get("id", "UNKNOWN"),
                    field_path=raw.get("field_path", ""),
                    condition=raw.get("condition", "required"),
                    severity=raw.get("severity", "warning"),
                    message=raw.get("message", ""),
                    params=raw.get("params", {}),
                    semantic_id=raw.get("semantic_id"),
                )
            )

        self._rulesets[category] = _LoadedRuleset(
            category=category,
            version=version,
            description=description,
            rules=rules,
        )
        logger.info(
            "ruleset_loaded",
            category=category,
            rule_count=len(rules),
            file=path.name,
        )


class _LoadedRuleset:
    """Internal holder for a parsed ruleset."""

    __slots__ = ("category", "version", "description", "rules")

    def __init__(
        self,
        category: str,
        version: str,
        description: str,
        rules: list[RuleDefinition],
    ) -> None:
        self.category = category
        self.version = version
        self.description = description
        self.rules = rules
