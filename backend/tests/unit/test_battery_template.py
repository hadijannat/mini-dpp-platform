"""Tests for Battery Passport template, ESPR tier visibility, and compliance rules."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.modules.compliance.engine import ComplianceEngine
from app.modules.dpps.submodel_filter import CONSUMER_SUBMODELS
from app.modules.templates.catalog import (
    CORE_TEMPLATE_KEYS,
    TEMPLATE_CATALOG,
    get_template_descriptor,
)


class TestBatteryTemplateDescriptor:
    """Battery Passport template descriptor is registered correctly."""

    def test_battery_passport_in_catalog(self) -> None:
        assert "battery-passport" in TEMPLATE_CATALOG

    def test_battery_passport_in_core_keys(self) -> None:
        assert "battery-passport" in CORE_TEMPLATE_KEYS

    def test_semantic_id(self) -> None:
        desc = TEMPLATE_CATALOG["battery-passport"]
        assert desc.semantic_id == ("https://admin-shell.io/idta/BatteryPassport/BatteryPass/1/0")

    def test_repo_folder(self) -> None:
        desc = TEMPLATE_CATALOG["battery-passport"]
        assert desc.repo_folder == "Battery Passport"

    def test_aasx_pattern(self) -> None:
        desc = TEMPLATE_CATALOG["battery-passport"]
        assert "02035" in desc.aasx_pattern
        assert "BatteryPassport" in desc.aasx_pattern

    def test_get_template_descriptor_returns_battery(self) -> None:
        desc = get_template_descriptor("battery-passport")
        assert desc is not None
        assert desc.key == "battery-passport"
        assert desc.title == "Battery Passport"

    def test_baseline_version(self) -> None:
        desc = TEMPLATE_CATALOG["battery-passport"]
        assert desc.baseline_major == 1
        assert desc.baseline_minor == 0

    def test_support_policy_marks_template_unavailable(self) -> None:
        desc = TEMPLATE_CATALOG["battery-passport"]
        assert desc.support_status == "unavailable"
        assert desc.refresh_enabled is False


class TestBatteryESPRTier:
    """Battery Passport submodels are consumer-visible per EU 2023/1542."""

    def test_battery_prefix_in_consumer_submodels(self) -> None:
        assert any(
            prefix.startswith("https://admin-shell.io/idta/BatteryPassport")
            for prefix in CONSUMER_SUBMODELS
        )

    def test_consumer_submodels_count(self) -> None:
        # Registry-driven mapping may include legacy aliases and exact semantic IDs.
        assert len(CONSUMER_SUBMODELS) >= 4


class TestBatteryComplianceRules:
    """Battery compliance rules load and validate correctly."""

    def test_batteries_yaml_exists(self) -> None:
        rules_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "app"
            / "modules"
            / "compliance"
            / "rules"
        )
        batteries_path = rules_dir / "batteries.yaml"
        assert batteries_path.exists()

    def test_batteries_yaml_parses(self) -> None:
        rules_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "app"
            / "modules"
            / "compliance"
            / "rules"
        )
        batteries_path = rules_dir / "batteries.yaml"
        with open(batteries_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        assert data["category"] == "battery"
        assert isinstance(data["rules"], list)

    def test_new_battery_passport_rules_present(self) -> None:
        rules_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "app"
            / "modules"
            / "compliance"
            / "rules"
        )
        batteries_path = rules_dir / "batteries.yaml"
        with open(batteries_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        rule_ids = {r["id"] for r in data["rules"]}
        for bat_id in ("BAT-060", "BAT-061", "BAT-062", "BAT-063", "BAT-064", "BAT-065"):
            assert bat_id in rule_ids, f"{bat_id} missing from batteries.yaml"

    def test_rule_ids_are_unique(self) -> None:
        rules_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "app"
            / "modules"
            / "compliance"
            / "rules"
        )
        batteries_path = rules_dir / "batteries.yaml"
        with open(batteries_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        rule_ids = [r["id"] for r in data["rules"]]
        assert len(rule_ids) == len(set(rule_ids)), "Duplicate rule IDs found"

    def test_engine_loads_battery_rules(self) -> None:
        engine = ComplianceEngine()
        ruleset = engine.get_category_ruleset("battery")
        assert ruleset is not None
        assert len(ruleset.rules) >= 21  # 15 original + 6 new

    def test_engine_battery_rules_have_valid_severity(self) -> None:
        engine = ComplianceEngine()
        ruleset = engine.get_category_ruleset("battery")
        assert ruleset is not None
        for rule in ruleset.rules:
            assert rule.severity in ("critical", "warning", "info")
