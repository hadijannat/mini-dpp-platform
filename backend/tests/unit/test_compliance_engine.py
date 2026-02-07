"""Unit tests for the ESPR compliance rule engine."""

from __future__ import annotations

from typing import Any

from app.modules.compliance.categories import detect_category
from app.modules.compliance.engine import ComplianceEngine
from app.modules.compliance.schemas import RuleDefinition
from app.modules.compliance.validators.base import CategoryValidator
from app.modules.compliance.validators.battery import BatteryValidator
from app.modules.compliance.validators.electronic import ElectronicValidator
from app.modules.compliance.validators.textile import TextileValidator

# ---------------------------------------------------------------------------
# Fixtures / Helpers
# ---------------------------------------------------------------------------


def _make_submodel(
    id_short: str,
    semantic_id: str,
    elements: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a minimal AAS submodel dict."""
    return {
        "idShort": id_short,
        "semanticId": {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": semantic_id}],
        },
        "modelType": "Submodel",
        "submodelElements": elements or [],
    }


def _make_property(id_short: str, value: Any = None) -> dict[str, Any]:
    return {
        "idShort": id_short,
        "modelType": "Property",
        "value": value,
    }


def _make_mlp(id_short: str, values: dict[str, str] | None = None) -> dict[str, Any]:
    lang_values = [{"language": lang, "text": text} for lang, text in (values or {}).items()]
    return {
        "idShort": id_short,
        "modelType": "MultiLanguageProperty",
        "value": lang_values,
    }


def _make_collection(id_short: str, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "idShort": id_short,
        "modelType": "SubmodelElementCollection",
        "value": children or [],
    }


def _battery_env(**overrides: Any) -> dict[str, Any]:
    """Build a minimal battery AAS environment."""
    elements = [
        _make_property("ManufacturerIdentification", overrides.get("manufacturer", "ACME")),
        _make_property("BatteryModel", overrides.get("model", "LFP-100")),
        _make_property("BatteryWeight", overrides.get("weight", "45.2")),
        _make_property("BatteryCategory", overrides.get("category", "Industrial")),
        _make_property("DateOfManufacturing", overrides.get("date", "2024-01-15")),
    ]
    return {
        "assetAdministrationShells": [],
        "submodels": [
            _make_submodel(
                "GeneralProductInformation",
                "https://admin-shell.io/idta/BatteryPassport/GeneralProductInformation/1/0",
                elements,
            ),
        ],
    }


# ---------------------------------------------------------------------------
# Category Detection
# ---------------------------------------------------------------------------


class TestCategoryDetection:
    def test_detect_battery(self) -> None:
        env = _battery_env()
        assert detect_category(env) == "battery"

    def test_detect_textile(self) -> None:
        env: dict[str, Any] = {
            "submodels": [
                _make_submodel(
                    "TextileInfo",
                    "https://admin-shell.io/idta/TextilePassport/Info/1/0",
                ),
            ],
        }
        assert detect_category(env) == "textile"

    def test_detect_electronic(self) -> None:
        env: dict[str, Any] = {
            "submodels": [
                _make_submodel(
                    "ElectronicInfo",
                    "https://admin-shell.io/idta/ElectronicPassport/Info/1/0",
                ),
            ],
        }
        assert detect_category(env) == "electronic"

    def test_detect_unknown(self) -> None:
        env: dict[str, Any] = {
            "submodels": [
                _make_submodel("Something", "https://example.com/unknown/1/0"),
            ],
        }
        assert detect_category(env) is None

    def test_detect_empty(self) -> None:
        assert detect_category({}) is None
        assert detect_category({"submodels": []}) is None

    def test_detect_no_submodels_key(self) -> None:
        assert detect_category({"assetAdministrationShells": []}) is None


# ---------------------------------------------------------------------------
# Base Validator — Field Resolution
# ---------------------------------------------------------------------------


class TestBaseValidatorFieldResolution:
    def test_resolve_top_level_property(self) -> None:
        env = _battery_env(manufacturer="ACME Corp")
        validator = CategoryValidator()
        rule = RuleDefinition(
            id="TEST-1",
            field_path="GeneralProductInformation.ManufacturerIdentification",
            condition="required",
            severity="critical",
            message="test",
        )
        value = validator._resolve_field(env, rule)
        assert value == "ACME Corp"

    def test_resolve_missing_element(self) -> None:
        env = _battery_env()
        validator = CategoryValidator()
        rule = RuleDefinition(
            id="TEST-2",
            field_path="GeneralProductInformation.NonExistentField",
            condition="required",
            severity="critical",
            message="test",
        )
        value = validator._resolve_field(env, rule)
        assert value is None

    def test_resolve_nested_collection(self) -> None:
        env: dict[str, Any] = {
            "submodels": [
                _make_submodel(
                    "Performance",
                    "https://admin-shell.io/idta/BatteryPassport/PerformanceAndDurability/1/0",
                    [
                        _make_collection(
                            "RatedCapacity",
                            [
                                _make_property("Value", "100"),
                                _make_property("Unit", "Ah"),
                            ],
                        ),
                    ],
                ),
            ],
        }
        validator = CategoryValidator()
        rule = RuleDefinition(
            id="TEST-3",
            field_path="Performance.RatedCapacity.Value",
            condition="required",
            severity="critical",
            message="test",
        )
        value = validator._resolve_field(env, rule)
        assert value == "100"

    def test_resolve_with_semantic_id_filter(self) -> None:
        env: dict[str, Any] = {
            "submodels": [
                _make_submodel(
                    "GeneralProductInformation",
                    "https://admin-shell.io/idta/BatteryPassport/GeneralProductInformation/1/0",
                    [_make_property("BatteryModel", "LFP-100")],
                ),
                _make_submodel(
                    "GeneralProductInformation",
                    "https://example.com/other/1/0",
                    [_make_property("BatteryModel", "WRONG")],
                ),
            ],
        }
        validator = CategoryValidator()
        rule = RuleDefinition(
            id="TEST-4",
            field_path="GeneralProductInformation.BatteryModel",
            condition="required",
            severity="critical",
            message="test",
            semantic_id="https://admin-shell.io/idta/BatteryPassport/GeneralProductInformation/1/0",
        )
        value = validator._resolve_field(env, rule)
        assert value == "LFP-100"

    def test_resolve_missing_submodel(self) -> None:
        env: dict[str, Any] = {"submodels": []}
        validator = CategoryValidator()
        rule = RuleDefinition(
            id="TEST-5",
            field_path="NonExistent.Field",
            condition="required",
            severity="critical",
            message="test",
        )
        value = validator._resolve_field(env, rule)
        assert value is None

    def test_resolve_mlp_value(self) -> None:
        env: dict[str, Any] = {
            "submodels": [
                _make_submodel(
                    "Info",
                    "https://example.com/info/1/0",
                    [_make_mlp("Description", {"en": "Hello", "de": "Hallo"})],
                ),
            ],
        }
        validator = CategoryValidator()
        rule = RuleDefinition(
            id="TEST-6",
            field_path="Info.Description",
            condition="required",
            severity="warning",
            message="test",
        )
        value = validator._resolve_field(env, rule)
        assert isinstance(value, dict)
        assert value["en"] == "Hello"


# ---------------------------------------------------------------------------
# Condition Checks
# ---------------------------------------------------------------------------


class TestConditionChecks:
    def setup_method(self) -> None:
        self.validator = CategoryValidator()

    def _rule(self, condition: str, **kwargs: Any) -> RuleDefinition:
        return RuleDefinition(
            id="TEST",
            field_path="X.Y",
            condition=condition,
            severity="critical",
            message="test msg",
            params=kwargs,
        )

    def test_required_passes_with_value(self) -> None:
        assert self.validator._check_condition(self._rule("required"), "hello") is None

    def test_required_fails_with_none(self) -> None:
        v = self.validator._check_condition(self._rule("required"), None)
        assert v is not None
        assert v.rule_id == "TEST"

    def test_required_fails_with_empty_string(self) -> None:
        v = self.validator._check_condition(self._rule("required"), "  ")
        assert v is not None

    def test_required_fails_with_empty_list(self) -> None:
        v = self.validator._check_condition(self._rule("required"), [])
        assert v is not None

    def test_min_length_passes(self) -> None:
        r = self._rule("min_length", min_length=3)
        assert self.validator._check_condition(r, "abc") is None

    def test_min_length_fails(self) -> None:
        r = self._rule("min_length", min_length=5)
        v = self.validator._check_condition(r, "ab")
        assert v is not None

    def test_regex_passes(self) -> None:
        r = self._rule("regex", pattern=r"^\d{4}-\d{2}-\d{2}$")
        assert self.validator._check_condition(r, "2024-01-15") is None

    def test_regex_fails(self) -> None:
        r = self._rule("regex", pattern=r"^\d{4}-\d{2}-\d{2}$")
        v = self.validator._check_condition(r, "not-a-date")
        assert v is not None

    def test_enum_passes(self) -> None:
        r = self._rule("enum", allowed_values=["A", "B", "C"])
        assert self.validator._check_condition(r, "B") is None

    def test_enum_fails(self) -> None:
        r = self._rule("enum", allowed_values=["A", "B", "C"])
        v = self.validator._check_condition(r, "D")
        assert v is not None

    def test_range_passes(self) -> None:
        r = self._rule("range", min=0, max=100)
        assert self.validator._check_condition(r, "50") is None

    def test_range_fails_below_min(self) -> None:
        r = self._rule("range", min=10, max=100)
        v = self.validator._check_condition(r, "5")
        assert v is not None

    def test_range_fails_above_max(self) -> None:
        r = self._rule("range", min=0, max=100)
        v = self.validator._check_condition(r, "200")
        assert v is not None

    def test_range_fails_non_numeric(self) -> None:
        r = self._rule("range", min=0, max=100)
        v = self.validator._check_condition(r, "abc")
        assert v is not None

    def test_unknown_condition_no_violation(self) -> None:
        r = self._rule("unknown_cond")
        assert self.validator._check_condition(r, "anything") is None


# ---------------------------------------------------------------------------
# Compliance Engine (integration with YAML rules)
# ---------------------------------------------------------------------------


class TestComplianceEngine:
    def setup_method(self) -> None:
        self.engine = ComplianceEngine()

    def test_engine_loads_rulesets(self) -> None:
        categories = self.engine.list_categories()
        assert "battery" in categories
        assert "textile" in categories
        assert "electronic" in categories

    def test_evaluate_battery_compliant(self) -> None:
        """A battery env with all required Part 1 fields should pass those rules."""
        env = _battery_env()
        report = self.engine.evaluate(env, category="battery")
        # Only Part 1 fields are present — other parts will have violations
        assert report.category == "battery"
        # The 5 Part 1 fields we provided should pass
        part1_rule_ids = {"BAT-001", "BAT-002", "BAT-003", "BAT-004", "BAT-005"}
        violated_ids = {v.rule_id for v in report.violations}
        assert not part1_rule_ids.intersection(violated_ids)

    def test_evaluate_battery_missing_fields(self) -> None:
        """An empty battery env should produce critical violations."""
        env: dict[str, Any] = {
            "submodels": [
                _make_submodel(
                    "GeneralProductInformation",
                    "https://admin-shell.io/idta/BatteryPassport/GeneralProductInformation/1/0",
                    [],
                ),
            ],
        }
        report = self.engine.evaluate(env, category="battery")
        assert not report.is_compliant
        assert report.summary.critical_violations > 0
        # BAT-001 through BAT-005 should all be violated
        violated_ids = {v.rule_id for v in report.violations}
        assert "BAT-001" in violated_ids

    def test_evaluate_auto_detect_battery(self) -> None:
        """Category should be auto-detected from semantic IDs."""
        env = _battery_env()
        report = self.engine.evaluate(env)  # no explicit category
        assert report.category == "battery"

    def test_evaluate_unknown_category(self) -> None:
        """Unknown category returns empty compliant report."""
        env: dict[str, Any] = {"submodels": []}
        report = self.engine.evaluate(env, category="unknown")
        assert report.is_compliant
        assert report.summary.total_rules == 0

    def test_evaluate_no_category_detected(self) -> None:
        """When no category is detected, returns compliant report for 'unknown'."""
        env: dict[str, Any] = {
            "submodels": [
                _make_submodel("Foo", "https://example.com/foo/1/0"),
            ],
        }
        report = self.engine.evaluate(env)
        assert report.category == "unknown"
        assert report.is_compliant

    def test_get_category_ruleset(self) -> None:
        ruleset = self.engine.get_category_ruleset("battery")
        assert ruleset is not None
        assert ruleset.category == "battery"
        assert ruleset.version == "1.0"
        assert len(ruleset.rules) > 0

    def test_get_category_ruleset_nonexistent(self) -> None:
        assert self.engine.get_category_ruleset("nonexistent") is None

    def test_get_all_rules(self) -> None:
        all_rules = self.engine.get_all_rules()
        assert "battery" in all_rules
        assert "textile" in all_rules
        assert "electronic" in all_rules

    def test_report_summary_counts(self) -> None:
        """Verify summary counts are consistent."""
        env = _battery_env()
        report = self.engine.evaluate(env, category="battery")
        total = report.summary.total_rules
        passed = report.summary.passed
        critical = report.summary.critical_violations
        warnings = report.summary.warnings
        info = report.summary.info
        assert total == passed + critical + warnings + info

    def test_violation_has_field_path(self) -> None:
        env: dict[str, Any] = {
            "submodels": [
                _make_submodel(
                    "GeneralProductInformation",
                    "https://admin-shell.io/idta/BatteryPassport/GeneralProductInformation/1/0",
                    [],
                ),
            ],
        }
        report = self.engine.evaluate(env, category="battery")
        for v in report.violations:
            assert v.field_path
            assert v.message
            assert v.severity in ("critical", "warning", "info")


# ---------------------------------------------------------------------------
# Per-Category Validators
# ---------------------------------------------------------------------------


class TestCategoryValidators:
    def test_battery_validator_category(self) -> None:
        assert BatteryValidator().category == "battery"

    def test_textile_validator_category(self) -> None:
        assert TextileValidator().category == "textile"

    def test_electronic_validator_category(self) -> None:
        assert ElectronicValidator().category == "electronic"

    def test_battery_validator_returns_violations(self) -> None:
        v = BatteryValidator()
        rules = [
            RuleDefinition(
                id="BAT-TEST",
                field_path="GeneralProductInformation.Missing",
                condition="required",
                severity="critical",
                message="test",
            ),
        ]
        env = _battery_env()
        violations = v.validate(env, rules)
        assert len(violations) == 1
        assert violations[0].rule_id == "BAT-TEST"

    def test_textile_validator_no_violations_when_present(self) -> None:
        v = TextileValidator()
        rules = [
            RuleDefinition(
                id="TXT-TEST",
                field_path="TextileInfo.ManufacturerName",
                condition="required",
                severity="critical",
                message="test",
            ),
        ]
        env: dict[str, Any] = {
            "submodels": [
                _make_submodel(
                    "TextileInfo",
                    "https://admin-shell.io/idta/TextilePassport/Info/1/0",
                    [_make_property("ManufacturerName", "FabricCo")],
                ),
            ],
        }
        violations = v.validate(env, rules)
        assert len(violations) == 0


# ---------------------------------------------------------------------------
# Engine with custom rules directory
# ---------------------------------------------------------------------------


class TestEngineCustomRulesDir:
    def test_nonexistent_dir_loads_empty(self, tmp_path: Any) -> None:
        engine = ComplianceEngine(rules_dir=tmp_path / "nonexistent")
        assert engine.list_categories() == []

    def test_custom_yaml_rule_loaded(self, tmp_path: Any) -> None:
        rule_yaml = tmp_path / "custom.yaml"
        rule_yaml.write_text(
            """
category: custom
version: "0.1"
description: "Test custom rules"
rules:
  - id: CUST-001
    field_path: "Foo.Bar"
    condition: required
    severity: critical
    message: "Bar is required"
"""
        )
        engine = ComplianceEngine(rules_dir=tmp_path)
        assert "custom" in engine.list_categories()
        ruleset = engine.get_category_ruleset("custom")
        assert ruleset is not None
        assert len(ruleset.rules) == 1
        assert ruleset.rules[0].id == "CUST-001"

    def test_invalid_yaml_skipped(self, tmp_path: Any) -> None:
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("- just a list\n- not a dict")
        engine = ComplianceEngine(rules_dir=tmp_path)
        assert engine.list_categories() == []

    def test_evaluate_with_custom_rules(self, tmp_path: Any) -> None:
        rule_yaml = tmp_path / "custom.yaml"
        rule_yaml.write_text(
            """
category: custom
version: "0.1"
description: "Test"
rules:
  - id: CUST-001
    field_path: "Info.Name"
    condition: required
    severity: critical
    message: "Name required"
  - id: CUST-002
    field_path: "Info.Weight"
    condition: range
    severity: warning
    message: "Weight out of range"
    params:
      min: 0
      max: 1000
"""
        )
        engine = ComplianceEngine(rules_dir=tmp_path)
        env: dict[str, Any] = {
            "submodels": [
                _make_submodel(
                    "Info",
                    "https://example.com/info/1/0",
                    [
                        _make_property("Name", "Widget"),
                        _make_property("Weight", "500"),
                    ],
                ),
            ],
        }
        report = engine.evaluate(env, category="custom")
        assert report.is_compliant
        assert report.summary.total_rules == 2
        assert report.summary.passed == 2
