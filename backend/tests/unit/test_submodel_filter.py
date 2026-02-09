"""Tests for ESPR tiered access control in submodel_filter."""

from __future__ import annotations

from app.modules.dpps.submodel_filter import (
    ESPR_TIER_SUBMODEL_MAP,
    filter_aas_env_by_espr_tier,
)


def _make_submodel(semantic_id: str | None = None) -> dict:
    """Create a minimal submodel dict with optional semantic ID."""
    sm: dict = {"idShort": "TestSubmodel", "id": "urn:test:sm:1"}
    if semantic_id is not None:
        sm["semanticId"] = {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": semantic_id}],
        }
    return sm


def _make_env(*submodels: dict) -> dict:
    return {
        "assetAdministrationShells": [],
        "submodels": list(submodels),
        "conceptDescriptions": [],
    }


class TestEsprTierFiltering:
    """Verify ESPR tier access control behavior."""

    def test_none_tier_defaults_to_consumer(self) -> None:
        """espr_tier=None should default to consumer tier (deny-by-default)."""
        sm = _make_submodel("https://example.com/unknown/semantic/id")
        env = _make_env(sm)
        result = filter_aas_env_by_espr_tier(env, None)
        # Consumer tier only sees specific prefixes — unknown should be filtered
        assert len(result["submodels"]) == 0

    def test_consumer_tier_filters_non_consumer_submodels(self) -> None:
        """Consumer tier should only see consumer-allowed submodels."""
        sm_unknown = _make_submodel("https://example.com/unknown")
        env = _make_env(sm_unknown)
        result = filter_aas_env_by_espr_tier(env, "consumer")
        assert len(result["submodels"]) == 0

    def test_manufacturer_tier_sees_all(self) -> None:
        """Manufacturer tier has full access."""
        sm = _make_submodel("https://example.com/anything")
        env = _make_env(sm)
        result = filter_aas_env_by_espr_tier(env, "manufacturer")
        assert len(result["submodels"]) == 1

    def test_authority_tier_sees_all(self) -> None:
        """Market surveillance authority has full access."""
        sm = _make_submodel("https://example.com/anything")
        env = _make_env(sm)
        result = filter_aas_env_by_espr_tier(env, "market_surveillance_authority")
        assert len(result["submodels"]) == 1

    def test_unknown_tier_gets_nothing(self) -> None:
        """Unknown tier should get empty submodel list (deny-by-default)."""
        sm = _make_submodel("https://example.com/anything")
        env = _make_env(sm)
        result = filter_aas_env_by_espr_tier(env, "alien_tier")
        assert len(result["submodels"]) == 0

    def test_submodel_without_semantic_id_denied(self) -> None:
        """Submodels without semantic IDs should NOT be visible (was True, now False)."""
        sm = _make_submodel(None)
        env = _make_env(sm)
        result = filter_aas_env_by_espr_tier(env, "consumer")
        assert len(result["submodels"]) == 0

    def test_submodel_without_semantic_id_visible_to_manufacturer(self) -> None:
        """Manufacturer tier sees all submodels regardless of semantic ID."""
        sm = _make_submodel(None)
        env = _make_env(sm)
        result = filter_aas_env_by_espr_tier(env, "manufacturer")
        assert len(result["submodels"]) == 1

    def test_in_place_mutation(self) -> None:
        """in_place=True should mutate the original dict."""
        sm = _make_submodel("https://example.com/unknown")
        env = _make_env(sm)
        result = filter_aas_env_by_espr_tier(env, "consumer", in_place=True)
        assert result is env
        assert len(env["submodels"]) == 0

    def test_empty_string_tier_defaults_to_consumer(self) -> None:
        """espr_tier='' should default to consumer tier (deny-by-default)."""
        sm = _make_submodel("https://example.com/unknown")
        env = _make_env(sm)
        result = filter_aas_env_by_espr_tier(env, "")
        assert len(result["submodels"]) == 0

    def test_whitespace_only_tier_defaults_to_consumer(self) -> None:
        """espr_tier='  ' should default to consumer tier (deny-by-default)."""
        sm = _make_submodel("https://example.com/unknown")
        env = _make_env(sm)
        result = filter_aas_env_by_espr_tier(env, "   ")
        assert len(result["submodels"]) == 0

    def test_tier_map_completeness(self) -> None:
        """All expected tiers should be in the tier map."""
        expected = {"consumer", "recycler", "market_surveillance_authority", "manufacturer"}
        assert set(ESPR_TIER_SUBMODEL_MAP.keys()) == expected
