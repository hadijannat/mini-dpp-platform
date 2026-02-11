import io
import json
from unittest.mock import MagicMock

from basyx.aas import model
from basyx.aas.adapter import json as basyx_json

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


def test_instantiate_element_strips_list_item_id_short_for_roundtrip() -> None:
    builder = BasyxDppBuilder(MagicMock())

    template_item = model.Property(
        id_short=None,
        value_type=model.datatypes.String,
        value=None,
    )
    template_list = model.SubmodelElementList(
        id_short="PcfCalculationMethods",
        order_relevant=True,
        type_value_list_element=model.Property,
        value_type_list_element=model.datatypes.String,
        value=[template_item],
    )

    instantiated = builder._instantiate_element(template_list, ["GHG"])
    assert isinstance(instantiated, model.SubmodelElementList)

    store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
    aas = model.AssetAdministrationShell(
        id_="urn:aas:test:1",
        id_short="AAS1",
        asset_information=model.AssetInformation(
            asset_kind=model.AssetKind.INSTANCE,
            global_asset_id="urn:asset:test:1",
        ),
        submodel=set(),
    )
    submodel = model.Submodel(
        id_="urn:sm:test:1",
        id_short="SM1",
        submodel_element=[instantiated],
    )
    store.add(aas)
    store.add(submodel)
    aas.submodel.add(model.ModelReference.from_referable(submodel))

    payload = basyx_json.object_store_to_json(store)  # type: ignore[attr-defined]
    json_payload = json.loads(payload)
    list_item = json_payload["submodels"][0]["submodelElements"][0]["value"][0]
    assert "idShort" not in list_item

    basyx_json.read_aas_json_file(io.StringIO(payload), failsafe=False)  # type: ignore[attr-defined]
