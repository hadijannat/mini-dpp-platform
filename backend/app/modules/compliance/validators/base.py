"""Base class for per-category compliance validators."""

from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger
from app.modules.compliance.schemas import ComplianceViolation, RuleDefinition

logger = get_logger(__name__)


class CategoryValidator:
    """Base validator that evaluates rules against an AAS environment dict.

    Subclasses may override ``validate`` to add category-specific logic
    beyond the standard condition checks.
    """

    category: str = ""

    def validate(
        self,
        aas_env: dict[str, Any],
        rules: list[RuleDefinition],
    ) -> list[ComplianceViolation]:
        """Evaluate all *rules* against *aas_env* and return violations."""
        violations: list[ComplianceViolation] = []
        for rule in rules:
            value = self._resolve_field(aas_env, rule)
            violation = self._check_condition(rule, value)
            if violation is not None:
                violations.append(violation)
        return violations

    # ------------------------------------------------------------------
    # Field resolution
    # ------------------------------------------------------------------

    def _resolve_field(
        self,
        aas_env: dict[str, Any],
        rule: RuleDefinition,
    ) -> Any:
        """Walk the AAS environment to find the value at *rule.field_path*.

        The field_path uses the format:
            ``<submodel_idShort>.<element_path_with_dots>``

        For example:
            ``GeneralProductInformation.BatteryCapacity``
            ``PerformanceAndDurability.RatedCapacity.Value``

        If ``rule.semantic_id`` is set, only submodels whose semanticId
        matches that value are considered.
        """
        submodels = aas_env.get("submodels")
        if not isinstance(submodels, list):
            return None

        parts = rule.field_path.split(".")
        if not parts:
            return None

        submodel_id_short = parts[0]
        element_path = parts[1:]

        for submodel in submodels:
            if not isinstance(submodel, dict):
                continue
            # Match by idShort
            if submodel.get("idShort") != submodel_id_short:
                continue
            # Optionally filter by semantic ID
            if rule.semantic_id and not self._semantic_id_matches(
                submodel, rule.semantic_id
            ):
                continue
            # Walk into submodelElements
            return self._walk_elements(
                submodel.get("submodelElements", []),
                element_path,
            )

        return None

    def _walk_elements(
        self,
        elements: list[Any],
        path: list[str],
    ) -> Any:
        """Recursively walk submodelElements to find a value."""
        if not path:
            return elements  # return the container itself

        target = path[0]
        remaining = path[1:]

        for element in elements:
            if not isinstance(element, dict):
                continue
            if element.get("idShort") != target:
                continue

            if not remaining:
                return self._extract_value(element)

            # Recurse into children
            model_type = self._get_model_type(element)
            if model_type == "SubmodelElementCollection":
                children = element.get("value", [])
                if isinstance(children, list):
                    return self._walk_elements(children, remaining)
            elif model_type == "Entity":
                children = element.get("statements", [])
                if isinstance(children, list):
                    return self._walk_elements(children, remaining)

            return None

        return None

    # ------------------------------------------------------------------
    # Value extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_value(element: dict[str, Any]) -> Any:
        """Extract the effective value from an AAS element."""
        model_type = CategoryValidator._get_model_type(element)
        if model_type == "MultiLanguageProperty":
            values = element.get("value")
            if isinstance(values, list):
                return {
                    entry.get("language", ""): entry.get("text", "")
                    for entry in values
                    if isinstance(entry, dict)
                }
            return values
        if model_type == "Range":
            return {"min": element.get("min"), "max": element.get("max")}
        if model_type in ("File", "Blob"):
            return element.get("value")
        if model_type in ("SubmodelElementCollection", "SubmodelElementList"):
            return element.get("value")
        return element.get("value")

    @staticmethod
    def _get_model_type(element: dict[str, Any]) -> str:
        """Normalise modelType to a plain string."""
        raw = element.get("modelType", "")
        if isinstance(raw, dict):
            return str(raw.get("name", ""))
        return str(raw)

    @staticmethod
    def _semantic_id_matches(submodel: dict[str, Any], expected: str) -> bool:
        sem_id = submodel.get("semanticId")
        if not isinstance(sem_id, dict):
            return False
        keys = sem_id.get("keys")
        if not isinstance(keys, list) or not keys:
            return False
        first = keys[0]
        if not isinstance(first, dict):
            return False
        return str(first.get("value", "")) == expected

    # ------------------------------------------------------------------
    # Condition evaluation
    # ------------------------------------------------------------------

    def _check_condition(
        self,
        rule: RuleDefinition,
        value: Any,
    ) -> ComplianceViolation | None:
        """Evaluate the rule condition against the resolved value."""
        condition = rule.condition
        if condition == "required":
            if self._is_empty(value):
                return self._violation(rule, value)
        elif condition == "min_length":
            min_len = int(rule.params.get("min_length", 1))
            if self._is_empty(value) or (isinstance(value, str) and len(value) < min_len):
                return self._violation(rule, value)
        elif condition == "regex":
            pattern = rule.params.get("pattern", "")
            if self._is_empty(value) or (
                isinstance(value, str) and not re.search(pattern, value)
            ):
                return self._violation(rule, value)
        elif condition == "enum":
            allowed = rule.params.get("allowed_values", [])
            if not isinstance(allowed, list):
                allowed = [allowed]
            if self._is_empty(value) or value not in allowed:
                return self._violation(rule, value)
        elif condition == "range":
            return self._check_range(rule, value)
        else:
            logger.warning("unknown_condition", condition=condition, rule_id=rule.id)

        return None

    def _check_range(
        self,
        rule: RuleDefinition,
        value: Any,
    ) -> ComplianceViolation | None:
        """Evaluate a numeric range condition."""
        if self._is_empty(value):
            return self._violation(rule, value)
        try:
            num = float(value)
        except (TypeError, ValueError):
            return self._violation(rule, value)
        min_val = rule.params.get("min")
        max_val = rule.params.get("max")
        if min_val is not None and num < float(min_val):
            return self._violation(rule, value)
        if max_val is not None and num > float(max_val):
            return self._violation(rule, value)
        return None

    @staticmethod
    def _is_empty(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        return bool(isinstance(value, (list, dict)) and not value)

    @staticmethod
    def _violation(rule: RuleDefinition, actual_value: Any) -> ComplianceViolation:
        return ComplianceViolation(
            rule_id=rule.id,
            severity=rule.severity,
            field_path=rule.field_path,
            message=rule.message,
            actual_value=actual_value,
        )
