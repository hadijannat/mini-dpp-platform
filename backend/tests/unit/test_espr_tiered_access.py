"""Tests for ESPR tiered access submodel filtering."""

from __future__ import annotations

from app.modules.dpps.submodel_filter import (
    CONSUMER_SUBMODELS,
    RECYCLER_SUBMODELS,
    filter_aas_env_by_espr_tier,
)


def _make_submodel(sm_id: str, semantic_prefix: str) -> dict:
    """Build a minimal submodel dict with a semantic ID."""
    return {
        "id": sm_id,
        "idShort": sm_id,
        "semanticId": {
            "type": "ExternalReference",
            "keys": [{"type": "Submodel", "value": semantic_prefix + "/V1.0"}],
        },
        "submodelElements": [],
    }


def _make_aas_env(*submodels: dict) -> dict:
    return {
        "assetAdministrationShells": [],
        "submodels": list(submodels),
    }


class TestConsumerTier:
    """Consumer tier should only see nameplate/technicaldata/carbon submodels."""

    def test_filters_to_consumer_visible(self) -> None:
        env = _make_aas_env(
            _make_submodel("sm1", "https://admin-shell.io/zvei/nameplate"),
            _make_submodel("sm2", "https://admin-shell.io/idta/CarbonFootprint"),
            _make_submodel("sm3", "https://admin-shell.io/idta/MaterialComposition"),
        )
        filtered = filter_aas_env_by_espr_tier(env, "consumer")
        ids = [sm["id"] for sm in filtered["submodels"]]
        assert "sm1" in ids
        assert "sm2" in ids
        assert "sm3" not in ids

    def test_consumer_keeps_technical_data(self) -> None:
        env = _make_aas_env(
            _make_submodel("sm1", "https://admin-shell.io/idta/TechnicalData"),
        )
        filtered = filter_aas_env_by_espr_tier(env, "consumer")
        assert len(filtered["submodels"]) == 1


class TestRecyclerTier:
    """Recycler tier extends consumer visibility."""

    def test_recycler_includes_consumer_submodels(self) -> None:
        env = _make_aas_env(
            _make_submodel("sm1", "https://admin-shell.io/zvei/nameplate"),
            _make_submodel("sm2", "https://admin-shell.io/idta/CarbonFootprint"),
        )
        filtered = filter_aas_env_by_espr_tier(env, "recycler")
        assert len(filtered["submodels"]) == 2

    def test_recycler_still_hides_unknown(self) -> None:
        env = _make_aas_env(
            _make_submodel("sm1", "https://admin-shell.io/zvei/nameplate"),
            _make_submodel("secret", "https://example.com/internal/secret"),
        )
        filtered = filter_aas_env_by_espr_tier(env, "recycler")
        ids = [sm["id"] for sm in filtered["submodels"]]
        assert "sm1" in ids
        assert "secret" not in ids


class TestFullAccessTiers:
    """Authority and manufacturer tiers see everything."""

    def test_authority_sees_all(self) -> None:
        env = _make_aas_env(
            _make_submodel("sm1", "https://admin-shell.io/zvei/nameplate"),
            _make_submodel("secret", "https://example.com/internal/secret"),
        )
        filtered = filter_aas_env_by_espr_tier(env, "market_surveillance_authority")
        assert len(filtered["submodels"]) == 2

    def test_manufacturer_sees_all(self) -> None:
        env = _make_aas_env(
            _make_submodel("sm1", "https://admin-shell.io/zvei/nameplate"),
            _make_submodel("secret", "https://example.com/internal/secret"),
        )
        filtered = filter_aas_env_by_espr_tier(env, "manufacturer")
        assert len(filtered["submodels"]) == 2


class TestNoneTier:
    """None tier = backwards compatible, no filtering."""

    def test_none_tier_returns_full_env(self) -> None:
        env = _make_aas_env(
            _make_submodel("sm1", "https://admin-shell.io/zvei/nameplate"),
            _make_submodel("secret", "https://example.com/internal/secret"),
        )
        result = filter_aas_env_by_espr_tier(env, None)
        assert len(result["submodels"]) == 2

    def test_none_tier_does_not_deepcopy(self) -> None:
        env = _make_aas_env(
            _make_submodel("sm1", "https://admin-shell.io/zvei/nameplate"),
        )
        result = filter_aas_env_by_espr_tier(env, None)
        # Should be the same object (no copy for performance)
        assert result is env


class TestNoSemanticId:
    """Submodels without semanticId should be visible to all tiers."""

    def test_no_semantic_id_visible_to_consumer(self) -> None:
        sm = {"id": "sm1", "idShort": "Unknown", "submodelElements": []}
        env = _make_aas_env(sm)
        filtered = filter_aas_env_by_espr_tier(env, "consumer")
        assert len(filtered["submodels"]) == 1

    def test_empty_keys_visible_to_consumer(self) -> None:
        sm = {
            "id": "sm1",
            "idShort": "Unknown",
            "semanticId": {"type": "ExternalReference", "keys": []},
            "submodelElements": [],
        }
        env = _make_aas_env(sm)
        filtered = filter_aas_env_by_espr_tier(env, "consumer")
        assert len(filtered["submodels"]) == 1


class TestUnknownTier:
    """Unknown tier string should return full env (not in map)."""

    def test_unknown_tier_returns_full_env(self) -> None:
        env = _make_aas_env(
            _make_submodel("sm1", "https://admin-shell.io/zvei/nameplate"),
            _make_submodel("secret", "https://example.com/internal/secret"),
        )
        # Unknown tier is not in ESPR_TIER_SUBMODEL_MAP, get() returns None
        # but get() returns None which means "full access"
        filtered = filter_aas_env_by_espr_tier(env, "unknown_tier")
        # "unknown_tier" is not in the map, so get() returns None -> full access
        assert len(filtered["submodels"]) == 2


class TestTierSets:
    """Verify tier set relationships."""

    def test_recycler_is_superset_of_consumer(self) -> None:
        assert CONSUMER_SUBMODELS.issubset(RECYCLER_SUBMODELS)
