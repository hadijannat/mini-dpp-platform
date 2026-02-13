from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.db.models import DPPStatus
from app.modules.export.router import BatchExportRequest, batch_export


def _tenant(*, is_publisher: bool) -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=uuid4(),
        tenant_slug="default",
        user=SimpleNamespace(sub="user-1"),
        is_publisher=is_publisher,
    )


def _dpp(dpp_id) -> SimpleNamespace:
    return SimpleNamespace(
        id=dpp_id,
        owner_subject="owner-1",
        status=DPPStatus.DRAFT,
        visibility_scope="owner_team",
    )


@pytest.mark.asyncio()
async def test_batch_export_requires_access_per_item() -> None:
    dpp_id = uuid4()
    body = BatchExportRequest(dpp_ids=[dpp_id], format="json")
    tenant = _tenant(is_publisher=True)
    dpp_service = SimpleNamespace(
        get_dpp=AsyncMock(return_value=_dpp(dpp_id)),
        is_resource_shared_with_user=AsyncMock(return_value=False),
        get_latest_revision=AsyncMock(return_value=SimpleNamespace(aas_env_json={})),
    )
    export_service = SimpleNamespace(
        export_json=MagicMock(return_value=b"{}"),
        export_aasx=MagicMock(return_value=b""),
    )
    epcis_service = SimpleNamespace(get_for_dpp=AsyncMock(return_value=[]))

    with (
        patch("app.modules.export.router.DPPService", return_value=dpp_service),
        patch("app.modules.export.router.ExportService", return_value=export_service),
        patch("app.modules.export.router.EPCISService", return_value=epcis_service),
        patch(
            "app.modules.export.router.require_access",
            new=AsyncMock(
                side_effect=HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden",
                )
            ),
        ) as require_access_mock,
        patch("app.modules.export.router.emit_audit_event", new=AsyncMock()),
    ):
        response = await batch_export(
            body=body,
            request=SimpleNamespace(base_url="http://localhost:8000/"),
            db=AsyncMock(),
            tenant=tenant,
        )

    require_access_mock.assert_awaited_once()
    export_service.export_json.assert_not_called()
    assert response.headers["X-Batch-Succeeded"] == "0"
    assert response.headers["X-Batch-Failed"] == "1"

    with zipfile.ZipFile(io.BytesIO(response.body), "r") as archive:
        assert archive.namelist() == []


@pytest.mark.asyncio()
async def test_batch_export_aasx_requires_publisher_role() -> None:
    dpp_id = uuid4()
    body = BatchExportRequest(dpp_ids=[dpp_id], format="aasx")
    tenant = _tenant(is_publisher=False)
    dpp_service = SimpleNamespace(
        get_dpp=AsyncMock(return_value=_dpp(dpp_id)),
        is_resource_shared_with_user=AsyncMock(return_value=False),
        get_latest_revision=AsyncMock(return_value=SimpleNamespace(aas_env_json={})),
    )
    export_service = SimpleNamespace(
        export_json=MagicMock(return_value=b"{}"),
        export_aasx=MagicMock(return_value=b"aasx-bytes"),
    )
    epcis_service = SimpleNamespace(get_for_dpp=AsyncMock(return_value=[]))

    with (
        patch("app.modules.export.router.DPPService", return_value=dpp_service),
        patch("app.modules.export.router.ExportService", return_value=export_service),
        patch("app.modules.export.router.EPCISService", return_value=epcis_service),
        patch("app.modules.export.router.require_access", new=AsyncMock()) as require_access_mock,
        patch("app.modules.export.router.emit_audit_event", new=AsyncMock()),
    ):
        response = await batch_export(
            body=body,
            request=SimpleNamespace(base_url="http://localhost:8000/"),
            db=AsyncMock(),
            tenant=tenant,
        )

    require_access_mock.assert_awaited_once()
    dpp_service.get_latest_revision.assert_not_awaited()
    export_service.export_aasx.assert_not_called()
    assert response.headers["X-Batch-Succeeded"] == "0"
    assert response.headers["X-Batch-Failed"] == "1"


@pytest.mark.asyncio()
async def test_batch_export_authorized_item_is_included_in_zip() -> None:
    dpp_id = uuid4()
    body = BatchExportRequest(dpp_ids=[dpp_id], format="json")
    tenant = _tenant(is_publisher=True)
    dpp_service = SimpleNamespace(
        get_dpp=AsyncMock(return_value=_dpp(dpp_id)),
        is_resource_shared_with_user=AsyncMock(return_value=False),
        get_latest_revision=AsyncMock(return_value=SimpleNamespace(aas_env_json={})),
    )
    export_service = SimpleNamespace(
        export_json=MagicMock(return_value=b'{"ok": true}'),
        export_aasx=MagicMock(return_value=b""),
    )
    epcis_service = SimpleNamespace(get_for_dpp=AsyncMock(return_value=[]))

    with (
        patch("app.modules.export.router.DPPService", return_value=dpp_service),
        patch("app.modules.export.router.ExportService", return_value=export_service),
        patch("app.modules.export.router.EPCISService", return_value=epcis_service),
        patch("app.modules.export.router.require_access", new=AsyncMock()),
        patch("app.modules.export.router.emit_audit_event", new=AsyncMock()),
    ):
        response = await batch_export(
            body=body,
            request=SimpleNamespace(base_url="http://localhost:8000/"),
            db=AsyncMock(),
            tenant=tenant,
        )

    assert response.headers["X-Batch-Succeeded"] == "1"
    assert response.headers["X-Batch-Failed"] == "0"
    with zipfile.ZipFile(io.BytesIO(response.body), "r") as archive:
        assert archive.namelist() == [f"dpp-{dpp_id}.json"]
