import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
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


def _store_to_env(store: model.DictObjectStore[model.Identifiable]) -> dict[str, object]:
    payload = basyx_json.object_store_to_json(store)  # type: ignore[attr-defined]
    return json.loads(payload)


def test_update_submodel_environment_backfills_empty_collection_structure() -> None:
    builder = BasyxDppBuilder(MagicMock())

    aas = model.AssetAdministrationShell(
        id_="urn:aas:test:2",
        id_short="AAS2",
        asset_information=model.AssetInformation(
            asset_kind=model.AssetKind.INSTANCE,
            global_asset_id="urn:asset:test:2",
        ),
        submodel=set(),
    )
    existing_submodel = model.Submodel(
        id_="urn:sm:test:nameplate",
        id_short="Nameplate",
        semantic_id=_ref("https://admin-shell.io/idta/nameplate/3/0/Nameplate"),
        submodel_element=[
            model.SubmodelElementCollection(
                id_short="AddressInformation",
                semantic_id=_ref(
                    "https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/AddressInformation"
                ),
                value=[],
            )
        ],
    )
    existing_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
    existing_store.add(aas)
    existing_store.add(existing_submodel)
    aas.submodel.add(model.ModelReference.from_referable(existing_submodel))
    existing_env = _store_to_env(existing_store)

    template_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
    template_submodel = model.Submodel(
        id_="urn:template:nameplate",
        id_short="Nameplate",
        semantic_id=_ref("https://admin-shell.io/idta/nameplate/3/0/Nameplate"),
        submodel_element=[
            model.SubmodelElementCollection(
                id_short="AddressInformation",
                semantic_id=_ref(
                    "https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/AddressInformation"
                ),
                value=[
                    model.Property(
                        id_short="Street",
                        value_type=model.datatypes.String,
                        value=None,
                    ),
                    model.Property(
                        id_short="CityTown",
                        value_type=model.datatypes.String,
                        value=None,
                    ),
                ],
            )
        ],
    )
    template_store.add(template_submodel)
    template_env = _store_to_env(template_store)

    template = SimpleNamespace(
        template_key="digital-nameplate",
        idta_version="3.0.1",
        template_aasx=None,
        template_json=template_env,
    )

    updated = builder.update_submodel_environment(
        aas_env_json=existing_env,
        template_key="digital-nameplate",
        template=template,
        submodel_data={
            "AddressInformation": {
                "Street": "Example Street 1",
                "CityTown": "Berlin",
            }
        },
        asset_ids={"manufacturerPartId": "P-1"},
        rebuild_from_template=False,
    )

    submodels = updated.get("submodels", [])
    assert submodels
    submodel_elements = submodels[0].get("submodelElements", [])
    address = next(
        element for element in submodel_elements if element.get("idShort") == "AddressInformation"
    )
    nested = {entry.get("idShort"): entry.get("value") for entry in address.get("value", [])}
    assert nested["Street"] == "Example Street 1"
    assert nested["CityTown"] == "Berlin"


def test_update_submodel_environment_rejects_invalid_file_mime_type() -> None:
    builder = BasyxDppBuilder(MagicMock())

    aas = model.AssetAdministrationShell(
        id_="urn:aas:test:file",
        id_short="AASFile",
        asset_information=model.AssetInformation(
            asset_kind=model.AssetKind.INSTANCE,
            global_asset_id="urn:asset:test:file",
        ),
        submodel=set(),
    )
    submodel = model.Submodel(
        id_="urn:sm:test:file",
        id_short="Nameplate",
        semantic_id=_ref("https://admin-shell.io/idta/nameplate/3/0/Nameplate"),
        submodel_element=[
            model.File(
                id_short="ArbitraryFile",
                content_type="application/pdf",
                value=None,
            )
        ],
    )
    existing_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
    existing_store.add(aas)
    existing_store.add(submodel)
    aas.submodel.add(model.ModelReference.from_referable(submodel))
    existing_env = _store_to_env(existing_store)

    template_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
    template_submodel = model.Submodel(
        id_="urn:template:file",
        id_short="Nameplate",
        semantic_id=_ref("https://admin-shell.io/idta/nameplate/3/0/Nameplate"),
        submodel_element=[
            model.File(
                id_short="ArbitraryFile",
                content_type="application/pdf",
                value=None,
            )
        ],
    )
    template_store.add(template_submodel)
    template_env = _store_to_env(template_store)

    template = SimpleNamespace(
        template_key="digital-nameplate",
        idta_version="3.0.1",
        template_aasx=None,
        template_json=template_env,
    )

    with pytest.raises(ValueError, match="Invalid MIME type"):
        builder.update_submodel_environment(
            aas_env_json=existing_env,
            template_key="digital-nameplate",
            template=template,
            submodel_data={
                "ArbitraryFile": {
                    "contentType": "not a mime",
                    "value": "https://example.test/file.pdf",
                }
            },
            asset_ids={"manufacturerPartId": "P-1"},
            rebuild_from_template=False,
        )
