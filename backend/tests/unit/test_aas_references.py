"""Unit tests for shared AAS reference utilities."""

from basyx.aas import model

from app.modules.aas.references import (
    extract_semantic_id_str,
    reference_from_dict,
    reference_to_dict,
    reference_to_str,
)

# ---------------------------------------------------------------------------
# reference_to_str
# ---------------------------------------------------------------------------


class TestReferenceToStr:
    def test_none_returns_none(self) -> None:
        assert reference_to_str(None) is None

    def test_external_reference(self) -> None:
        ref = model.ExternalReference(
            key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:example:value"),)
        )
        assert reference_to_str(ref) == "urn:example:value"

    def test_model_reference(self) -> None:
        ref = model.ModelReference(
            key=(model.Key(model.KeyTypes.SUBMODEL, "urn:sm:1"),),
            type_=model.Submodel,
        )
        assert reference_to_str(ref) == "urn:sm:1"

    def test_single_key_returns_value(self) -> None:
        """References must have at least one key in BaSyx; test with a single key."""
        ref = model.ExternalReference(
            key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:only:key"),)
        )
        assert reference_to_str(ref) == "urn:only:key"


# ---------------------------------------------------------------------------
# reference_to_dict
# ---------------------------------------------------------------------------


class TestReferenceToDict:
    def test_none_returns_none(self) -> None:
        assert reference_to_dict(None) is None

    def test_external_reference_serialization(self) -> None:
        ref = model.ExternalReference(
            key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:example:1"),)
        )
        result = reference_to_dict(ref)
        assert result is not None
        assert result["type"] == "ExternalReference"
        assert len(result["keys"]) == 1
        assert result["keys"][0]["type"] == "GLOBAL_REFERENCE"
        assert result["keys"][0]["value"] == "urn:example:1"

    def test_model_reference_serialization(self) -> None:
        ref = model.ModelReference(
            key=(model.Key(model.KeyTypes.SUBMODEL, "urn:sm:1"),),
            type_=model.Submodel,
        )
        result = reference_to_dict(ref)
        assert result is not None
        assert result["type"] == "ModelReference"
        assert result["keys"][0]["type"] == "SUBMODEL"

    def test_multi_key_serialization(self) -> None:
        """References with multiple keys serialize all of them."""
        ref = model.ExternalReference(
            key=(
                model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:k1"),
                model.Key(model.KeyTypes.FRAGMENT_REFERENCE, "frag"),
            )
        )
        result = reference_to_dict(ref)
        assert result is not None
        assert len(result["keys"]) == 2


# ---------------------------------------------------------------------------
# reference_from_dict — including ModelReference bug fix
# ---------------------------------------------------------------------------


class TestReferenceFromDict:
    def test_none_input(self) -> None:
        assert reference_from_dict(None) is None

    def test_non_dict_input(self) -> None:
        assert reference_from_dict("not a dict") is None

    def test_missing_keys(self) -> None:
        assert reference_from_dict({"type": "ExternalReference"}) is None

    def test_external_reference(self) -> None:
        payload = {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": "urn:example:1"}],
        }
        ref = reference_from_dict(payload)
        assert ref is not None
        assert isinstance(ref, model.ExternalReference)
        assert reference_to_str(ref) == "urn:example:1"

    def test_model_reference_constructed_correctly(self) -> None:
        """This was the bug — ModelReference should NOT be downgraded to ExternalReference."""
        payload = {
            "type": "ModelReference",
            "keys": [{"type": "Submodel", "value": "urn:sm:1"}],
        }
        ref = reference_from_dict(payload)
        assert ref is not None
        assert isinstance(ref, model.ModelReference), (
            f"Expected ModelReference, got {type(ref).__name__}"
        )
        assert reference_to_str(ref) == "urn:sm:1"

    def test_model_reference_with_property_key(self) -> None:
        payload = {
            "type": "ModelReference",
            "keys": [
                {"type": "Submodel", "value": "urn:sm:1"},
                {"type": "Property", "value": "SomeProperty"},
            ],
        }
        ref = reference_from_dict(payload)
        assert ref is not None
        assert isinstance(ref, model.ModelReference)

    def test_model_reference_global_key_falls_back_to_external(self) -> None:
        """When first key type has no model class mapping, fall back to ExternalReference."""
        payload = {
            "type": "ModelReference",
            "keys": [{"type": "GlobalReference", "value": "urn:global:1"}],
        }
        ref = reference_from_dict(payload)
        assert ref is not None
        assert isinstance(ref, model.ExternalReference)

    def test_no_type_defaults_to_external(self) -> None:
        payload = {
            "keys": [{"type": "GlobalReference", "value": "urn:global:1"}],
        }
        ref = reference_from_dict(payload)
        assert ref is not None
        assert isinstance(ref, model.ExternalReference)

    def test_invalid_key_type_skipped(self) -> None:
        payload = {
            "type": "ExternalReference",
            "keys": [{"type": "BogusType", "value": "urn:bogus"}],
        }
        assert reference_from_dict(payload) is None

    def test_round_trip_external(self) -> None:
        original = model.ExternalReference(
            key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:example:rt"),)
        )
        d = reference_to_dict(original)
        assert d is not None
        restored = reference_from_dict(d)
        assert restored is not None
        assert isinstance(restored, model.ExternalReference)
        assert reference_to_str(restored) == "urn:example:rt"

    def test_round_trip_model_reference(self) -> None:
        original = model.ModelReference(
            key=(model.Key(model.KeyTypes.SUBMODEL, "urn:sm:rt"),),
            type_=model.Submodel,
        )
        d = reference_to_dict(original)
        assert d is not None
        restored = reference_from_dict(d)
        assert restored is not None
        assert isinstance(restored, model.ModelReference)
        assert reference_to_str(restored) == "urn:sm:rt"


# ---------------------------------------------------------------------------
# extract_semantic_id_str
# ---------------------------------------------------------------------------


class TestExtractSemanticIdStr:
    def test_standard_structure(self) -> None:
        obj = {"semanticId": {"keys": [{"value": "urn:example:semantic"}]}}
        assert extract_semantic_id_str(obj) == "urn:example:semantic"

    def test_capital_d_variant(self) -> None:
        """Qualifiers may use semanticID with capital D."""
        obj = {"semanticID": {"keys": [{"value": "urn:example:qual"}]}}
        assert extract_semantic_id_str(obj) == "urn:example:qual"

    def test_empty_keys(self) -> None:
        obj = {"semanticId": {"keys": []}}
        assert extract_semantic_id_str(obj) == ""

    def test_missing_semantic_id(self) -> None:
        obj = {"idShort": "Test"}
        assert extract_semantic_id_str(obj) == ""

    def test_non_dict_semantic_id(self) -> None:
        obj = {"semanticId": "not-a-dict"}
        assert extract_semantic_id_str(obj) == ""
