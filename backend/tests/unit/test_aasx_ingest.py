from __future__ import annotations

import io
import json
import zipfile

import pytest
from basyx.aas import model
from basyx.aas.adapter import aasx

from app.modules.dpps.aasx_ingest import AasxIngestService


def _build_test_aasx(
    *,
    sidecar: dict | None = None,
    extra_archive_entries: dict[str, bytes] | None = None,
) -> bytes:
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
        id_short="Nameplate",
        submodel_element=[
            model.Property(
                id_short="ManufacturerName",
                value_type=model.datatypes.String,
                value="Example",
            )
        ],
    )
    store.add(aas)
    store.add(submodel)
    aas.submodel.add(model.ModelReference.from_referable(submodel))

    output = io.BytesIO()
    with aasx.AASXWriter(output) as writer:
        files = aasx.DictSupplementaryFileContainer()  # type: ignore[no-untyped-call]
        writer.write_all_aas_objects("/aasx/data.json", store, files, write_json=True)
    output.seek(0)
    with zipfile.ZipFile(output, mode="a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("aasx/files/manual.pdf", b"%PDF-1.4")
        if sidecar is not None:
            archive.writestr("aasx/files/ui-hints.json", json.dumps(sidecar))
        for path, payload in (extra_archive_entries or {}).items():
            archive.writestr(path, payload)
    return output.getvalue()


def _inject_uom_into_data_json(aasx_bytes: bytes) -> bytes:
    source = io.BytesIO(aasx_bytes)
    target = io.BytesIO()
    with (
        zipfile.ZipFile(source, "r") as archive,
        zipfile.ZipFile(target, mode="w", compression=zipfile.ZIP_DEFLATED) as output,
    ):
        for entry in archive.infolist():
            payload = archive.read(entry.filename)
            if entry.filename.replace("\\", "/").lstrip("/").lower() == "aasx/data.json":
                document = json.loads(payload.decode("utf-8"))
                document["conceptDescriptions"] = [
                    {
                        "id": "urn:unit:m",
                        "embeddedDataSpecifications": [
                            {
                                "dataSpecification": {
                                    "keys": [
                                        {
                                            "value": (
                                                "https://admin-shell.io/DataSpecificationTemplates/"
                                                "DataSpecificationUoM/3"
                                            )
                                        }
                                    ]
                                },
                                "dataSpecificationContent": {
                                    "modelType": "DataSpecificationUoM",
                                    "symbol": "m",
                                    "specificUnitID": "MTR",
                                    "classificationSystem": "UNECE Rec 20",
                                },
                            }
                        ],
                    }
                ]
                payload = json.dumps(document).encode("utf-8")
            output.writestr(entry.filename, payload)
    target.seek(0)
    return target.read()


def test_parse_aasx_extracts_supplementary_and_doc_hints() -> None:
    service = AasxIngestService()
    aasx_bytes = _build_test_aasx(
        sidecar={
            "mappings": {
                "hint-1": {
                    "semanticId": "https://example.com/ManufacturerName",
                    "helpText": "Read manufacturer section.",
                }
            }
        }
    )

    result = service.parse(aasx_bytes)

    assert result.aas_env_json.get("submodels")
    assert any(entry.package_path.endswith("manual.pdf") for entry in result.supplementary_files)
    assert result.doc_hints_manifest is not None
    assert "by_semantic_id" in result.doc_hints_manifest


def test_parse_aasx_rejects_ambiguous_doc_hints_semantic_ids() -> None:
    service = AasxIngestService()
    aasx_bytes = _build_test_aasx(
        sidecar={
            "mappings": {
                "hint-1": {"semanticId": "https://example.com/ManufacturerName"},
                "hint-2": {"semanticId": "https://example.com/ManufacturerName"},
            }
        }
    )

    with pytest.raises(ValueError, match="Ambiguous ui-hints mapping"):
        service.parse(aasx_bytes)


def test_parse_aasx_ignores_unsafe_supplementary_paths() -> None:
    service = AasxIngestService()
    aasx_bytes = _build_test_aasx(
        extra_archive_entries={
            "aasx/files/../../evil.txt": b"nope",
            "aasx/files/../sneaky.txt": b"nope-2",
        }
    )

    result = service.parse(aasx_bytes)

    paths = [entry.package_path for entry in result.supplementary_files]
    assert "/aasx/files/manual.pdf" in paths
    assert all(path.startswith("/aasx/files/") for path in paths)
    assert "/evil.txt" not in paths


def test_parse_aasx_falls_back_to_zip_when_strict_parse_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AasxIngestService()
    aasx_bytes = _inject_uom_into_data_json(_build_test_aasx())

    class _FailingReader:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> _FailingReader:
            return self

        def __exit__(
            self,
            _exc_type: object,
            _exc: object,
            _tb: object,
        ) -> None:
            return None

        def read_into(self, *_args: object, **_kwargs: object) -> None:
            raise ValueError("simulated strict parser failure")

    monkeypatch.setattr("app.modules.dpps.aasx_ingest.aasx.AASXReader", _FailingReader)

    result = service.parse(aasx_bytes)

    assert result.aas_env_json.get("submodels")
    concept_descriptions = result.aas_env_json.get("conceptDescriptions", [])
    assert isinstance(concept_descriptions, list)
    unit_cd = next(cd for cd in concept_descriptions if cd.get("id") == "urn:unit:m")
    assert unit_cd.get("embeddedDataSpecifications") == []
