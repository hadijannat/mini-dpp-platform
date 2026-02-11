from types import SimpleNamespace

from app.modules.dpps.submodel_binding import resolve_submodel_bindings


def test_resolve_submodel_bindings_semantic_exact() -> None:
    templates = [
        SimpleNamespace(
            template_key="carbon-footprint",
            semantic_id="https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0",
            idta_version="1.0.1",
            resolved_version="1.0.1",
        )
    ]
    aas_env = {
        "submodels": [
            {
                "id": "urn:dpp:sm:cf",
                "idShort": "CarbonFootprint",
                "semanticId": {
                    "keys": [
                        {
                            "type": "GlobalReference",
                            "value": "https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0",
                        }
                    ]
                },
            }
        ]
    }

    bindings = resolve_submodel_bindings(aas_env_json=aas_env, templates=templates)

    assert len(bindings) == 1
    assert bindings[0].template_key == "carbon-footprint"
    assert bindings[0].binding_source == "semantic_exact"
    assert bindings[0].submodel_id == "urn:dpp:sm:cf"


def test_resolve_submodel_bindings_semantic_alias() -> None:
    templates = [
        SimpleNamespace(
            template_key="digital-nameplate",
            semantic_id="https://admin-shell.io/idta/nameplate/3/0/Nameplate",
            idta_version="3.0.1",
            resolved_version="3.0.1",
        )
    ]
    aas_env = {
        "submodels": [
            {
                "id": "urn:dpp:sm:nameplate",
                "idShort": "Nameplate",
                "semanticId": {
                    "keys": [
                        {
                            "type": "GlobalReference",
                            "value": "https://admin-shell.io/zvei/nameplate/3/0/Nameplate",
                        }
                    ]
                },
            }
        ]
    }

    bindings = resolve_submodel_bindings(aas_env_json=aas_env, templates=templates)

    assert len(bindings) == 1
    assert bindings[0].template_key == "digital-nameplate"
    assert bindings[0].binding_source == "semantic_alias"


def test_resolve_submodel_bindings_id_short_fallback() -> None:
    templates = [
        SimpleNamespace(
            template_key="technical-data",
            semantic_id="0173-1#01-AHX837#002",
            idta_version="2.0.2",
            resolved_version="2.0.2",
        )
    ]
    aas_env = {
        "submodels": [
            {
                "id": "urn:dpp:sm:tech",
                "idShort": "TechnicalData",
                "submodelElements": [],
            }
        ]
    }

    bindings = resolve_submodel_bindings(aas_env_json=aas_env, templates=templates)

    assert len(bindings) == 1
    assert bindings[0].template_key == "technical-data"
    assert bindings[0].binding_source == "id_short"
