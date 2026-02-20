"""Tests for full IDTA catalog sync into template cache."""

from __future__ import annotations

import json
from typing import Any

import pytest
from basyx.aas import model
from basyx.aas.adapter import json as basyx_json

from app.modules.templates.service import TemplateRegistryService


class _FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, tree_payload: dict[str, Any], payload_by_name: dict[str, dict[str, Any]]) -> None:
        self._tree_payload = tree_payload
        self._payload_by_name = payload_by_name

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, _headers: dict[str, str] | None = None) -> _FakeResponse:
        if "git/trees/" in url:
            return _FakeResponse(self._tree_payload)
        for filename, payload in self._payload_by_name.items():
            if filename in url:
                return _FakeResponse(payload)
        return _FakeResponse({}, status_code=404)


def _ref(iri: str) -> model.Reference:
    return model.ExternalReference((model.Key(model.KeyTypes.GLOBAL_REFERENCE, iri),))


def _template_environment(semantic_id: str, property_name: str = "ManufacturerName") -> dict[str, Any]:
    submodel = model.Submodel(
        id_="urn:test:template",
        id_short="Template",
        semantic_id=_ref(semantic_id),
        kind=model.ModellingKind.TEMPLATE,
        submodel_element=[
            model.Property(
                id_short=property_name,
                value_type=model.datatypes.String,
                value=None,
            )
        ],
    )
    store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
    store.add(submodel)
    payload = basyx_json.object_store_to_json(store)  # type: ignore[attr-defined]
    return json.loads(payload)


@pytest.mark.asyncio
async def test_catalog_sync_ingests_published_and_deprecated_with_deterministic_keys(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TemplateRegistryService(db_session)

    tree_payload = {
        "tree": [
            {
                "path": "published/DigitalNameplate/3/0/1/nameplate_sample.json",
                "type": "blob",
                "sha": "sha-sample",
            },
            {
                "path": "published/DigitalNameplate/3/0/1/nameplate_template.json",
                "type": "blob",
                "sha": "sha-template",
            },
            {
                "path": "deprecated/LegacySubmodel/1/0/0/legacy_template.json",
                "type": "blob",
                "sha": "sha-legacy",
            },
        ]
    }

    payload_by_name = {
        # Invalid sample candidate should be ignored in favor of template candidate.
        "nameplate_sample.json": {"foo": "bar"},
        "nameplate_template.json": _template_environment(
            "https://admin-shell.io/zvei/nameplate/3/0/Nameplate",
        ),
        "legacy_template.json": _template_environment(
            "https://example.org/smt/legacy/1/0/Submodel",
            property_name="LegacyField",
        ),
    }

    def fake_client_factory(*_args: Any, **_kwargs: Any) -> _FakeAsyncClient:
        return _FakeAsyncClient(tree_payload, payload_by_name)
    monkeypatch.setattr("app.modules.templates.service.httpx.AsyncClient", fake_client_factory)

    stats = await service.sync_catalog(include_deprecated=True)

    assert stats.discovered == 2
    assert stats.ingested == 2
    assert stats.updated == 0
    assert stats.failed == 0

    published = await service.get_template("digital-nameplate", "3.0.1")
    assert published is not None
    assert published.catalog_status == "published"
    assert published.source_file_path == "published/DigitalNameplate/3/0/1/nameplate_template.json"

    # Deprecated semantic ID is unknown, so key should be deterministic dynamic key.
    deprecated_key = service._build_deterministic_catalog_key(
        semantic_id="https://example.org/smt/legacy/1/0/Submodel",
        folder="LegacySubmodel",
    )
    deprecated = await service.get_template(deprecated_key, "1.0.0")
    assert deprecated is not None
    assert deprecated.catalog_status == "deprecated"


@pytest.mark.asyncio
async def test_catalog_sync_second_run_is_idempotent(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    service = TemplateRegistryService(db_session)

    tree_payload = {
        "tree": [
            {
                "path": "published/DigitalNameplate/3/0/1/nameplate_template.json",
                "type": "blob",
                "sha": "sha-template",
            },
        ]
    }
    payload_by_name = {
        "nameplate_template.json": _template_environment(
            "https://admin-shell.io/zvei/nameplate/3/0/Nameplate",
        ),
    }

    def fake_client_factory(*_args: Any, **_kwargs: Any) -> _FakeAsyncClient:
        return _FakeAsyncClient(tree_payload, payload_by_name)
    monkeypatch.setattr("app.modules.templates.service.httpx.AsyncClient", fake_client_factory)

    first = await service.sync_catalog(include_deprecated=False)
    second = await service.sync_catalog(include_deprecated=False)

    assert first.discovered == 1
    assert first.ingested == 1
    assert second.discovered == 1
    assert second.ingested == 0
    assert second.updated == 0
    assert second.skipped == 1
