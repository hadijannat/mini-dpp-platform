"""Tests for the shared IDTA semantic registry accessors."""

from __future__ import annotations

from app.modules.semantic_registry import (
    get_dropin_bindings_for_semantic_id,
    get_template_registry_entry,
    get_template_semantic_id,
    get_template_support_status,
    is_template_refresh_enabled,
    list_dropin_bindings,
    list_espr_tier_prefixes,
    load_semantic_registry,
    resolve_known_template_key_by_semantic_id,
)


class TestLoadSemanticRegistry:
    """Registry JSON loads and has expected top-level structure."""

    def test_returns_dict(self) -> None:
        registry = load_semantic_registry()
        assert isinstance(registry, dict)

    def test_has_templates_key(self) -> None:
        registry = load_semantic_registry()
        assert "templates" in registry
        assert isinstance(registry["templates"], dict)

    def test_has_espr_tier_prefixes_key(self) -> None:
        registry = load_semantic_registry()
        assert "espr_tier_prefixes" in registry
        assert isinstance(registry["espr_tier_prefixes"], dict)

    def test_has_legacy_aliases_key(self) -> None:
        registry = load_semantic_registry()
        assert "legacy_semantic_id_aliases" in registry
        assert isinstance(registry["legacy_semantic_id_aliases"], dict)


class TestGetTemplateSemanticId:
    """get_template_semantic_id returns URLs for known templates."""

    def test_known_template_returns_url(self) -> None:
        sid = get_template_semantic_id("digital-nameplate")
        assert sid is not None
        assert "nameplate" in sid.lower() or "Nameplate" in sid

    def test_battery_passport_returns_url(self) -> None:
        sid = get_template_semantic_id("battery-passport")
        assert sid is not None
        assert "BatteryPass" in sid

    def test_missing_key_returns_none(self) -> None:
        assert get_template_semantic_id("nonexistent-template") is None


class TestGetTemplateRegistryEntry:
    """get_template_registry_entry returns full entry dicts."""

    def test_known_template_returns_dict(self) -> None:
        entry = get_template_registry_entry("digital-nameplate")
        assert isinstance(entry, dict)
        assert "semantic_id" in entry
        assert "espr_category" in entry

    def test_missing_key_returns_none(self) -> None:
        assert get_template_registry_entry("nonexistent") is None


class TestGetTemplateSupportStatus:
    """Support status returns correct values and defaults."""

    def test_supported_template(self) -> None:
        status = get_template_support_status("digital-nameplate")
        assert status == "supported"

    def test_unavailable_template(self) -> None:
        status = get_template_support_status("battery-passport")
        assert status == "unavailable"

    def test_missing_key_defaults_to_supported(self) -> None:
        status = get_template_support_status("nonexistent-template")
        assert status == "supported"


class TestIsTemplateRefreshEnabled:
    """Refresh flag returns correct values and defaults."""

    def test_supported_template_is_refreshable(self) -> None:
        assert is_template_refresh_enabled("digital-nameplate") is True

    def test_battery_passport_not_refreshable(self) -> None:
        assert is_template_refresh_enabled("battery-passport") is False

    def test_missing_key_defaults_to_true(self) -> None:
        assert is_template_refresh_enabled("nonexistent-template") is True


class TestListEsprTierPrefixes:
    """ESPR tier prefix lists return expected content."""

    def test_consumer_has_prefixes(self) -> None:
        prefixes = list_espr_tier_prefixes("consumer")
        assert len(prefixes) >= 7
        assert all(isinstance(p, str) for p in prefixes)

    def test_manufacturer_returns_empty(self) -> None:
        # Manufacturer tier has full access (empty prefix list = no filtering)
        prefixes = list_espr_tier_prefixes("manufacturer")
        assert prefixes == ()

    def test_unknown_tier_returns_empty(self) -> None:
        prefixes = list_espr_tier_prefixes("unknown_tier")
        assert prefixes == ()

    def test_consumer_includes_battery_prefix(self) -> None:
        prefixes = list_espr_tier_prefixes("consumer")
        assert any("BatteryPassport" in p for p in prefixes)


class TestLegacyAliases:
    """Legacy semantic ID aliases map correctly."""

    def test_catenax_samm_alias_exists(self) -> None:
        registry = load_semantic_registry()
        aliases = registry["legacy_semantic_id_aliases"]
        assert "urn:samm:io.catenax.battery.battery_pass:6.0.0#BatteryPass" in aliases

    def test_catenax_samm_maps_to_battery_passport(self) -> None:
        registry = load_semantic_registry()
        aliases = registry["legacy_semantic_id_aliases"]
        assert (
            aliases["urn:samm:io.catenax.battery.battery_pass:6.0.0#BatteryPass"]
            == "battery-passport"
        )

    def test_resolve_known_template_key_by_semantic_id_uses_registry_templates(self) -> None:
        resolved = resolve_known_template_key_by_semantic_id(
            "https://admin-shell.io/zvei/nameplate/3/0/Nameplate"
        )
        assert resolved == "digital-nameplate"

    def test_resolve_known_template_key_by_semantic_id_uses_legacy_aliases(self) -> None:
        resolved = resolve_known_template_key_by_semantic_id(
            "urn:samm:io.catenax.battery.battery_pass:6.0.0#BatteryPass"
        )
        assert resolved == "battery-passport"


class TestDropinBindings:
    """Drop-in bindings are registry-driven and discoverable by semantic ID."""

    def test_registry_contains_dropin_bindings_map(self) -> None:
        bindings = list_dropin_bindings()
        assert isinstance(bindings, dict)
        assert bindings

    def test_get_dropin_bindings_for_semantic_id_returns_entries(self) -> None:
        entries = get_dropin_bindings_for_semantic_id(
            "https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/AddressInformation"
        )
        assert entries
        first = entries[0]
        assert first.get("source_template_key") == "contact-information"
        assert isinstance(first.get("source_selector"), dict)

    def test_get_dropin_bindings_is_case_and_trailing_slash_insensitive(self) -> None:
        a = get_dropin_bindings_for_semantic_id(
            "https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/AddressInformation"
        )
        b = get_dropin_bindings_for_semantic_id(
            "HTTPS://ADMIN-SHELL.IO/ZVEI/NAMEPLATE/1/0/CONTACTINFORMATIONS/ADDRESSINFORMATION/"
        )
        assert a == b
