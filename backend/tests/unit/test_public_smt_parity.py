"""Parity tests for public SMT preview/export and diagnostics."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from basyx.aas import model
from basyx.aas.adapter import json as basyx_json

from app.db.models import Template
from app.modules.aas.conformance import AASValidationResult
from app.modules.templates.service import TemplateRegistryService


def _ref(iri: str) -> model.Reference:
    return model.ExternalReference((model.Key(model.KeyTypes.GLOBAL_REFERENCE, iri),))


def _template_environment(
    *, semantic_id: str, property_id_short: str = "ManufacturerName"
) -> dict[str, Any]:
    submodel = model.Submodel(
        id_="urn:template:nameplate",
        id_short="Nameplate",
        semantic_id=_ref(semantic_id),
        kind=model.ModellingKind.TEMPLATE,
        submodel_element=[
            model.Property(
                id_short=property_id_short,
                value_type=model.datatypes.String,
                value=None,
                qualifier=[
                    model.Qualifier(
                        type_="SMT/Cardinality",
                        value_type=model.datatypes.String,
                        value="One",
                    )
                ],
            )
        ],
    )
    store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
    store.add(submodel)
    payload = basyx_json.object_store_to_json(store)  # type: ignore[attr-defined]
    return json.loads(payload)


async def _insert_template(
    db_session,
    *,
    template_key: str,
    version: str,
    semantic_id: str,
) -> Template:
    template = Template(
        template_key=template_key,
        display_name=template_key.replace("-", " ").title(),
        catalog_status="published",
        catalog_folder="Sandbox",
        idta_version=version,
        resolved_version=version,
        semantic_id=semantic_id,
        source_url=f"https://example.test/{template_key}/{version}.json",
        source_repo_ref="main",
        source_file_path=f"published/Sandbox/{template_key}.json",
        source_file_sha=f"sha-{template_key}-{version}",
        source_kind="json",
        selection_strategy="deterministic_v2",
        template_aasx=None,
        template_json=_template_environment(semantic_id=semantic_id),
        fetched_at=datetime.now(UTC),
    )
    db_session.add(template)
    await db_session.commit()
    return template


def _minimal_value_from_schema(schema: dict[str, Any]) -> Any:
    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        return schema["enum"][0]

    any_of = schema.get("anyOf")
    if isinstance(any_of, list) and any_of:
        for candidate in any_of:
            if isinstance(candidate, dict):
                candidate_type = candidate.get("type")
                if candidate_type != "null":
                    return _minimal_value_from_schema(candidate)

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), "object")

    if schema.get("x-multi-language"):
        required_languages = schema.get("x-required-languages")
        if isinstance(required_languages, list) and required_languages:
            return {str(lang): "value" for lang in required_languages if isinstance(lang, str)}
        return {"en": "value"}

    if schema.get("x-range"):
        return {"min": 0, "max": 0}

    if schema.get("x-file-upload"):
        return {"contentType": "application/pdf", "value": "https://example.org/file.pdf"}

    if schema.get("x-reference"):
        return {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": "https://example.org/ref"}],
        }

    if schema_type == "object":
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = schema.get("required") if isinstance(schema.get("required"), list) else []
        result: dict[str, Any] = {}
        for key in required:
            if not isinstance(key, str):
                continue
            child_schema = properties.get(key)
            if isinstance(child_schema, dict):
                result[key] = _minimal_value_from_schema(child_schema)
        return result

    if schema_type == "array":
        items = schema.get("items") if isinstance(schema.get("items"), dict) else {}
        min_items = schema.get("minItems") if isinstance(schema.get("minItems"), int) else 0
        if min_items > 0:
            return [_minimal_value_from_schema(items)]
        return []

    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0.0
    if schema_type == "boolean":
        return False

    if schema.get("format") == "uri":
        return "https://example.org/value"
    return "value"


@pytest.mark.asyncio
async def test_preview_export_never_return_raw_500_for_cached_templates(
    test_client, db_session
) -> None:
    await _insert_template(
        db_session,
        template_key="sandbox-nameplate",
        version="3.0.1",
        semantic_id="https://admin-shell.io/idta/nameplate/3/0/Nameplate",
    )
    await _insert_template(
        db_session,
        template_key="sandbox-contact-information",
        version="1.0.0",
        semantic_id="https://admin-shell.io/idta/ContactInformation/1/0",
    )
    await _insert_template(
        db_session,
        template_key="sandbox-technical-data",
        version="1.0.0",
        semantic_id="https://admin-shell.io/idta/TechnicalData/1/0",
    )

    templates_response = await test_client.get("/api/v1/public/smt/templates?status=all")
    assert templates_response.status_code == 200
    templates = templates_response.json()["templates"]
    assert templates

    for template in templates:
        template_key = template["template_key"]
        contract_response = await test_client.get(
            f"/api/v1/public/smt/templates/{template_key}/contract"
        )
        assert contract_response.status_code == 200
        contract_payload = contract_response.json()
        schema = contract_payload["schema"]
        payload = _minimal_value_from_schema(schema)
        assert isinstance(payload, dict)

        preview_response = await test_client.post(
            "/api/v1/public/smt/preview",
            json={
                "template_key": template_key,
                "data": payload,
            },
        )
        assert preview_response.status_code in {200, 422}
        assert preview_response.status_code != 500

        export_response = await test_client.post(
            "/api/v1/public/smt/export",
            json={
                "template_key": template_key,
                "data": payload,
                "format": "json",
            },
        )
        assert export_response.status_code in {200, 422}
        assert export_response.status_code != 500


@pytest.mark.asyncio
async def test_preview_builder_receives_full_template_lookup(
    test_client,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _insert_template(
        db_session,
        template_key="sandbox-main",
        version="3.0.1",
        semantic_id="https://admin-shell.io/idta/nameplate/3/0/Nameplate",
    )
    await _insert_template(
        db_session,
        template_key="sandbox-secondary",
        version="1.0.0",
        semantic_id="https://admin-shell.io/idta/ContactInformation/1/0",
    )

    captured: dict[str, list[str]] = {}

    def _capture_lookup(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        lookup = kwargs.get("template_lookup")
        if isinstance(lookup, dict):
            captured["keys"] = sorted(lookup.keys())
        return {"assetAdministrationShells": [], "submodels": [], "conceptDescriptions": []}

    monkeypatch.setattr(
        "app.modules.templates.public_router.TemplateInstanceBuilder.build_environment",
        _capture_lookup,
    )
    monkeypatch.setattr(
        "app.modules.templates.public_router.validate_aas_environment",
        lambda _aas_env: AASValidationResult(is_valid=True, errors=[], warnings=[]),
    )

    response = await test_client.post(
        "/api/v1/public/smt/preview",
        json={
            "template_key": "sandbox-main",
            "data": {"ManufacturerName": "ACME"},
        },
    )

    assert response.status_code == 200
    assert set(captured.get("keys", [])) >= {"sandbox-main", "sandbox-secondary"}


@pytest.mark.asyncio
async def test_unknown_model_types_are_reported_as_unsupported(db_session) -> None:
    service = TemplateRegistryService(db_session)
    definition = {
        "submodel": {
            "idShort": "TechnicalData",
            "elements": [
                {
                    "path": "TechnicalData.GenericItems",
                    "idShort": "GenericItems",
                    "modelType": "SubmodelElement",
                }
            ],
        }
    }
    schema = {
        "type": "object",
        "properties": {
            "GenericItems": {
                "type": "object",
                "x-readonly": True,
            }
        },
    }

    unsupported = service._collect_unsupported_nodes(
        definition=definition,
        schema=schema,
        strict_unknown_model_types=True,
    )

    assert unsupported
    assert unsupported[0]["modelType"] == "SubmodelElement"
    assert "unsupported_model_type:SubmodelElement" in unsupported[0]["reasons"]
