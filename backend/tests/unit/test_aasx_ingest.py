from __future__ import annotations

import io
import json
import zipfile

import pytest
from basyx.aas import model
from basyx.aas.adapter import aasx

from app.modules.dpps.aasx_ingest import AasxIngestService


def _build_test_aasx(*, sidecar: dict | None = None) -> bytes:
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
    return output.getvalue()


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
