from unittest.mock import MagicMock

from basyx.aas import model

from app.modules.dpps.basyx_builder import BasyxDppBuilder


def _ref(iri: str) -> model.Reference:
    return model.ExternalReference((model.Key(model.KeyTypes.GLOBAL_REFERENCE, iri),))


def test_find_submodel_uses_exact_semantic_id_match() -> None:
    builder = BasyxDppBuilder(MagicMock())
    store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()

    target = model.Submodel(
        id_="urn:test:submodel:1",
        id_short="Target",
        semantic_id=_ref("https://admin-shell.io/example/1/0/Target"),
        submodel_element=[],
    )
    similar = model.Submodel(
        id_="urn:test:submodel:2",
        id_short="Similar",
        semantic_id=_ref("https://admin-shell.io/example/1/0/TargetExtra"),
        submodel_element=[],
    )

    store.add(target)
    store.add(similar)

    found = builder._find_submodel(store, "https://admin-shell.io/example/1/0/Target")

    assert found is not None
    assert found.id_short == "Target"


def test_match_template_for_submodel_uses_exact_semantic_id_match() -> None:
    builder = BasyxDppBuilder(MagicMock())
    submodel = model.Submodel(
        id_="urn:test:submodel:3",
        id_short="T",
        semantic_id=_ref("https://admin-shell.io/example/1/0/Target"),
        submodel_element=[],
    )

    wrong = MagicMock()
    wrong.semantic_id = "https://admin-shell.io/example/1/0/TargetExtra"
    right = MagicMock()
    right.semantic_id = "https://admin-shell.io/example/1/0/Target"

    matched = builder._match_template_for_submodel(submodel, [wrong, right])

    assert matched is right
