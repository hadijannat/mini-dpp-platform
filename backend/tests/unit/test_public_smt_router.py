"""Tests for public SMT sandbox endpoints."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from basyx.aas import model
from basyx.aas.adapter import json as basyx_json

from app.core.config import get_settings
from app.db.models import Template
from app.modules.aas.conformance import AASValidationResult


def _ref(iri: str) -> model.Reference:
    return model.ExternalReference((model.Key(model.KeyTypes.GLOBAL_REFERENCE, iri),))


def _template_environment(
    *,
    semantic_id: str,
    property_id_short: str = "ManufacturerName",
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
    status: str = "published",
    version: str = "3.0.1",
    semantic_id: str = "https://admin-shell.io/idta/nameplate/3/0/Nameplate",
) -> Template:
    template = Template(
        template_key=template_key,
        display_name=template_key.replace("-", " ").title(),
        catalog_status=status,
        catalog_folder="Digital nameplate",
        idta_version=version,
        resolved_version=version,
        semantic_id=semantic_id,
        source_url=f"https://example.test/{template_key}/{version}.json",
        source_repo_ref="main",
        source_file_path=f"{status}/Digital nameplate/3/0/1/{template_key}.json",
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


@pytest.mark.asyncio
async def test_public_templates_list_reachable_without_auth(test_client, db_session) -> None:
    await _insert_template(db_session, template_key="digital-nameplate", status="published")

    response = await test_client.get("/api/v1/public/smt/templates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["templates"][0]["template_key"] == "digital-nameplate"


@pytest.mark.asyncio
async def test_public_contract_and_export_are_db_only_no_refresh(
    test_client,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _insert_template(db_session, template_key="digital-nameplate", status="published")
    refresh_spy = AsyncMock(side_effect=AssertionError("refresh_template should not be called"))
    monkeypatch.setattr(
        "app.modules.templates.service.TemplateRegistryService.refresh_template",
        refresh_spy,
    )

    contract_response = await test_client.get(
        "/api/v1/public/smt/templates/digital-nameplate/contract"
    )
    assert contract_response.status_code == 200

    export_response = await test_client.post(
        "/api/v1/public/smt/export",
        json={
            "template_key": "digital-nameplate",
            "data": {"ManufacturerName": "ACME"},
            "format": "json",
        },
    )
    assert export_response.status_code == 200
    assert refresh_spy.await_count == 0


@pytest.mark.asyncio
async def test_export_format_allowlist_rejects_unknown(test_client, db_session) -> None:
    await _insert_template(db_session, template_key="digital-nameplate", status="published")

    response = await test_client.post(
        "/api/v1/public/smt/export",
        json={
            "template_key": "digital-nameplate",
            "data": {"ManufacturerName": "ACME"},
            "format": "xml",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_payload_size_and_depth_limits(
    test_client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _insert_template(db_session, template_key="digital-nameplate", status="published")

    settings = get_settings()
    monkeypatch.setattr(settings, "public_smt_payload_max_bytes", 64)
    monkeypatch.setattr(settings, "public_smt_max_depth", 3)

    too_large_response = await test_client.post(
        "/api/v1/public/smt/preview",
        json={
            "template_key": "digital-nameplate",
            "data": {"ManufacturerName": "x" * 200},
        },
    )
    assert too_large_response.status_code == 413

    too_deep_response = await test_client.post(
        "/api/v1/public/smt/preview",
        json={
            "template_key": "digital-nameplate",
            "data": {"ManufacturerName": "ok", "a": {"b": {"c": {"d": 1}}}},
        },
    )
    assert too_deep_response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_schema_data_returns_actionable_errors(test_client, db_session) -> None:
    await _insert_template(db_session, template_key="digital-nameplate", status="published")

    response = await test_client.post(
        "/api/v1/public/smt/preview",
        json={
            "template_key": "digital-nameplate",
            "data": {},
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"]["code"] == "schema_validation_failed"
    assert payload["detail"]["errors"]


@pytest.mark.asyncio
async def test_metamodel_invalid_output_is_rejected(
    test_client,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _insert_template(db_session, template_key="digital-nameplate", status="published")

    def _invalid_validator(_aas_env: dict[str, Any]) -> AASValidationResult:
        return AASValidationResult(is_valid=False, errors=["invalid"], warnings=[])

    monkeypatch.setattr(
        "app.modules.templates.public_router.validate_aas_environment", _invalid_validator
    )

    response = await test_client.post(
        "/api/v1/public/smt/preview",
        json={
            "template_key": "digital-nameplate",
            "data": {"ManufacturerName": "ACME"},
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"]["code"] == "metamodel_validation_failed"


@pytest.mark.asyncio
async def test_preview_maps_instance_build_errors_to_structured_422(
    test_client,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _insert_template(db_session, template_key="digital-nameplate", status="published")

    def _raise_build_failure(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("build failed")

    monkeypatch.setattr(
        "app.modules.templates.public_router.TemplateInstanceBuilder.build_environment",
        _raise_build_failure,
    )

    response = await test_client.post(
        "/api/v1/public/smt/preview",
        json={
            "template_key": "digital-nameplate",
            "data": {"ManufacturerName": "ACME"},
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "instance_build_failed"
    assert detail["message"] == "Unable to build AAS instance from provided template data"
    assert detail["errors"][0]["path"] == "root"


@pytest.mark.asyncio
async def test_export_maps_instance_serialization_errors_to_structured_422(
    test_client,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _insert_template(db_session, template_key="digital-nameplate", status="published")

    def _mock_build_environment(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"assetAdministrationShells": [], "submodels": [], "conceptDescriptions": []}

    def _raise_serialization_failure(*_args: Any, **_kwargs: Any) -> bytes:
        raise RuntimeError("serialization failed")

    monkeypatch.setattr(
        "app.modules.templates.public_router.TemplateInstanceBuilder.build_environment",
        _mock_build_environment,
    )
    monkeypatch.setattr(
        "app.modules.templates.public_router.TemplateInstanceBuilder.to_json_bytes",
        _raise_serialization_failure,
    )
    monkeypatch.setattr(
        "app.modules.templates.public_router.validate_aas_environment",
        lambda _aas_env: AASValidationResult(is_valid=True, errors=[], warnings=[]),
    )

    response = await test_client.post(
        "/api/v1/public/smt/export",
        json={
            "template_key": "digital-nameplate",
            "data": {"ManufacturerName": "ACME"},
            "format": "json",
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "instance_serialization_failed"
    assert detail["message"] == "Unable to build AAS instance from provided template data"


@pytest.mark.asyncio
async def test_export_sets_sanitized_content_disposition_and_media_types(
    test_client,
    db_session,
) -> None:
    template_key = "dangerous/key"
    await _insert_template(db_session, template_key=template_key, status="published")

    for export_format, expected_media in (
        ("json", "application/json"),
        ("aasx", "application/asset-administration-shell-package+xml"),
        ("pdf", "application/pdf"),
    ):
        response = await test_client.post(
            "/api/v1/public/smt/export",
            json={
                "template_key": template_key,
                "data": {"ManufacturerName": "ACME"},
                "format": export_format,
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(expected_media)
        assert "attachment; filename=" in response.headers["content-disposition"]
        assert "/" not in response.headers["content-disposition"].split('"', 2)[1]


@pytest.mark.asyncio
async def test_status_filter_supports_published_and_deprecated(test_client, db_session) -> None:
    await _insert_template(db_session, template_key="published-template", status="published")
    await _insert_template(
        db_session,
        template_key="deprecated-template",
        status="deprecated",
        version="1.0.0",
        semantic_id="https://example.org/deprecated/1/0",
    )

    published_response = await test_client.get("/api/v1/public/smt/templates?status=published")
    deprecated_response = await test_client.get("/api/v1/public/smt/templates?status=deprecated")
    all_response = await test_client.get("/api/v1/public/smt/templates?status=all")

    assert published_response.status_code == 200
    assert deprecated_response.status_code == 200
    assert all_response.status_code == 200

    published_keys = {entry["template_key"] for entry in published_response.json()["templates"]}
    deprecated_keys = {entry["template_key"] for entry in deprecated_response.json()["templates"]}
    all_keys = {entry["template_key"] for entry in all_response.json()["templates"]}

    assert "published-template" in published_keys
    assert "deprecated-template" not in published_keys
    assert "deprecated-template" in deprecated_keys
    assert {"published-template", "deprecated-template"}.issubset(all_keys)
