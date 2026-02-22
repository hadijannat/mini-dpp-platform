from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.modules.dpps.router import import_dpp_aasx


class _UploadStub:
    def __init__(self, *, filename: str, chunks: list[bytes]) -> None:
        self.filename = filename
        self._chunks = chunks

    async def read(self, _size: int = -1) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


def _publisher_tenant() -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=uuid4(),
        tenant_slug="default",
        user=SimpleNamespace(sub="publisher-sub"),
        is_tenant_admin=False,
    )


@pytest.mark.asyncio()
async def test_import_aasx_rejects_payload_over_configured_limit() -> None:
    tenant = _publisher_tenant()
    file = _UploadStub(filename="payload.aasx", chunks=[b"abc", b"def"])

    with (
        patch("app.modules.dpps.router.require_access", new=AsyncMock()),
        patch(
            "app.modules.dpps.router.get_settings",
            return_value=SimpleNamespace(aasx_max_upload_bytes=5),
        ),
        patch("app.modules.dpps.router.AasxIngestService") as ingest_cls,
        pytest.raises(HTTPException) as exc_info,
    ):
        await import_dpp_aasx(
            request=MagicMock(),
            db=AsyncMock(),
            tenant=tenant,
            file=file,  # type: ignore[arg-type]
        )

    ingest_cls.assert_not_called()
    assert exc_info.value.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert "exceeds maximum upload size" in str(exc_info.value.detail)


@pytest.mark.asyncio()
async def test_import_aasx_sanitizes_parse_errors() -> None:
    tenant = _publisher_tenant()
    file = _UploadStub(filename="payload.aasx", chunks=[b"valid-ish", b""])
    ingest_service = SimpleNamespace(parse=MagicMock(side_effect=ValueError("boom /tmp/secret")))

    with (
        patch("app.modules.dpps.router.require_access", new=AsyncMock()),
        patch(
            "app.modules.dpps.router.get_settings",
            return_value=SimpleNamespace(aasx_max_upload_bytes=1024),
        ),
        patch("app.modules.dpps.router.AasxIngestService", return_value=ingest_service),
        pytest.raises(HTTPException) as exc_info,
    ):
        await import_dpp_aasx(
            request=MagicMock(),
            db=AsyncMock(),
            tenant=tenant,
            file=file,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert exc_info.value.detail == "Failed to parse AASX package"


@pytest.mark.asyncio()
async def test_import_aasx_strips_uom_before_validation() -> None:
    tenant = _publisher_tenant()
    file = _UploadStub(filename="payload.aasx", chunks=[b"valid-ish", b""])
    ingest_service = SimpleNamespace(
        parse=MagicMock(
            return_value=SimpleNamespace(
                aas_env_json={
                    "assetAdministrationShells": [],
                    "submodels": [
                        {"id": "urn:sm:1", "idShort": "Nameplate", "submodelElements": []}
                    ],
                    "conceptDescriptions": [
                        {
                            "id": "urn:unit:m",
                            "embeddedDataSpecifications": [
                                {
                                    "dataSpecification": {
                                        "keys": [
                                            {
                                                "value": (
                                                    "https://admin-shell.io/"
                                                    "DataSpecificationTemplates/"
                                                    "DataSpecificationUoM/3"
                                                )
                                            }
                                        ]
                                    },
                                    "dataSpecificationContent": {
                                        "modelType": "DataSpecificationUoM",
                                        "symbol": "m",
                                        "specificUnitID": "MTR",
                                    },
                                }
                            ],
                        }
                    ],
                },
                supplementary_files=[],
                doc_hints_manifest=None,
            )
        )
    )
    created_dpp = SimpleNamespace(
        id=uuid4(),
        status=SimpleNamespace(value="draft"),
        owner_subject=tenant.user.sub,
        visibility_scope=SimpleNamespace(value="owner_team"),
        asset_ids={"manufacturerPartId": "MP-1"},
        qr_payload="https://example.test/dpp",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    dpp_service = SimpleNamespace(
        extract_asset_ids_from_environment=MagicMock(
            return_value={"manufacturerPartId": "MP-1", "serialNumber": "S-1"}
        ),
        find_existing_dpp=AsyncMock(return_value=None),
        create_dpp_from_environment=AsyncMock(return_value=created_dpp),
        get_latest_revision=AsyncMock(return_value=SimpleNamespace()),
    )

    captured = {"uom_removed": None}

    def _validate(env: dict[str, object]) -> SimpleNamespace:
        concept_descriptions = env.get("conceptDescriptions", [])
        if isinstance(concept_descriptions, list):
            for cd in concept_descriptions:
                if isinstance(cd, dict) and cd.get("id") == "urn:unit:m":
                    captured["uom_removed"] = cd.get("embeddedDataSpecifications") == []
        return SimpleNamespace(is_valid=True, warnings=[], errors=[])

    with (
        patch("app.modules.dpps.router.require_access", new=AsyncMock()),
        patch(
            "app.modules.dpps.router.get_settings",
            return_value=SimpleNamespace(aasx_max_upload_bytes=1024),
        ),
        patch("app.modules.dpps.router.AasxIngestService", return_value=ingest_service),
        patch("app.modules.dpps.router.DPPService", return_value=dpp_service),
        patch("app.modules.dpps.router.validate_aas_environment", side_effect=_validate),
        patch("app.modules.dpps.router.load_users_by_subject", new=AsyncMock(return_value={})),
        patch("app.modules.dpps.router.emit_audit_event", new=AsyncMock()),
        patch("app.modules.dpps.router.trigger_webhooks", new=AsyncMock()),
        patch("app.modules.dpps.router.actor_payload", return_value={"subject": tenant.user.sub}),
    ):
        response = await import_dpp_aasx(
            request=MagicMock(),
            db=AsyncMock(),
            tenant=tenant,
            file=file,  # type: ignore[arg-type]
            master_product_id=None,
            master_version="latest",
        )

    assert response.id == created_dpp.id
    assert captured["uom_removed"] is True
