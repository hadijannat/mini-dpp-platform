"""Tests for AASX/JSON export structure."""

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.db.models import DPPRevision, RevisionState
from app.modules.export.service import ExportService


def _make_revision(dpp_id: UUID) -> DPPRevision:
    aas_env = {
        "assetAdministrationShells": [
            {
                "id": "urn:aas:1",
                "idShort": "TestAAS",
                "assetInformation": {
                    "assetKind": "Instance",
                    "globalAssetId": "urn:asset:1",
                    "specificAssetIds": [{"name": "manufacturerPartId", "value": "MP-1"}],
                },
                "submodelRefs": [
                    {
                        "type": "ModelReference",
                        "keys": [{"type": "Submodel", "value": "urn:sm:1"}],
                    }
                ],
            }
        ],
        "submodels": [
            {
                "id": "urn:sm:1",
                "idShort": "Nameplate",
                "semanticId": {
                    "type": "ExternalReference",
                    "keys": [
                        {
                            "type": "GlobalReference",
                            "value": "https://admin-shell.io/zvei/nameplate/2/0/Nameplate",
                        }
                    ],
                },
                "submodelElements": [],
            }
        ],
        "conceptDescriptions": [],
    }

    canonical = json.dumps(aas_env, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()

    return DPPRevision(
        dpp_id=dpp_id,
        revision_no=1,
        state=RevisionState.DRAFT,
        aas_env_json=aas_env,
        digest_sha256=digest,
        created_by_subject="test-user",
        created_at=datetime.now(UTC),
    )


def test_export_json_includes_metadata() -> None:
    export_service = ExportService()
    dpp_id = uuid4()
    revision = _make_revision(dpp_id)

    payload = json.loads(export_service.export_json(revision))

    assert "aasEnvironment" in payload
    assert "metadata" in payload
    assert payload["metadata"]["revisionNo"] == revision.revision_no
    assert payload["metadata"]["digestSha256"] == revision.digest_sha256


def test_export_aasx_structure_is_valid() -> None:
    export_service = ExportService()
    dpp_id = uuid4()
    revision = _make_revision(dpp_id)

    aasx_bytes = export_service.export_aasx(revision, dpp_id)

    validation = export_service.validate_aasx(aasx_bytes)
    assert validation["valid"] is True

    with zipfile.ZipFile(io.BytesIO(aasx_bytes), "r") as zf:
        names = set(zf.namelist())

    assert "[Content_Types].xml" in names
    assert "_rels/.rels" in names
    assert any(name in names for name in ("aasx/aas.json", "aasx/data.json")), (
        f"Expected AAS JSON part, got: {sorted(names)}"
    )
    assert any(
        name in names for name in ("aasx/_rels/aas.json.rels", "aasx/_rels/aasx-origin.rels")
    ), "Missing AASX origin relationships"
    assert "aasx/aasx-origin" in names
    assert any(name in names for name in ("metadata/core-properties.xml", "docProps/core.xml")), (
        "Missing core properties"
    )


def test_export_aasx_compliance_roundtrip() -> None:
    """Exported AASX passes BaSyx compliance validation (no hard errors)."""
    export_service = ExportService()
    dpp_id = uuid4()
    revision = _make_revision(dpp_id)

    aasx_bytes = export_service.export_aasx(revision, dpp_id)

    result = export_service.validate_aasx_compliance(aasx_bytes)
    assert result["valid"] is True, f"Compliance errors: {result['errors']}"


def test_validate_aasx_structure_delegates() -> None:
    """validate_aasx() delegates to validate_aasx_structure()."""
    export_service = ExportService()
    dpp_id = uuid4()
    revision = _make_revision(dpp_id)
    aasx_bytes = export_service.export_aasx(revision, dpp_id)

    result_old = export_service.validate_aasx(aasx_bytes)
    result_new = export_service.validate_aasx_structure(aasx_bytes)
    assert result_old == result_new
