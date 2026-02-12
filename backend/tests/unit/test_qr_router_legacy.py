"""Unit tests for legacy QR compatibility wrapper behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.db.models import DPPStatus
from app.modules.qr import router as qr_router
from app.modules.qr.schemas import CarrierFormat, CarrierOutputType, CarrierRequest


def _tenant_context(subject: str = "owner-sub") -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=uuid4(),
        tenant_slug="default",
        user=SimpleNamespace(sub=subject),
    )


def _published_dpp(dpp_id: UUID, *, asset_ids: dict[str, str]) -> SimpleNamespace:
    return SimpleNamespace(
        id=dpp_id,
        status=DPPStatus.PUBLISHED,
        owner_subject="owner-sub",
        visibility_scope="owner_team",
        asset_ids=asset_ids,
    )


@pytest.mark.asyncio
async def test_generate_carrier_gs1_legacy_uses_fallback_serial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dpp_id = uuid4()
    dpp = _published_dpp(dpp_id, asset_ids={"manufacturerPartId": "PART-001"})
    tenant = _tenant_context()

    dpp_service = MagicMock()
    dpp_service.get_dpp = AsyncMock(return_value=dpp)
    dpp_service.is_resource_shared_with_user = AsyncMock(return_value=False)

    qr_service = MagicMock()
    qr_service.extract_gtin_from_asset_ids.return_value = ("10614141000415", "", True)
    qr_service.build_gs1_digital_link.return_value = (
        f"https://id.gs1.org/01/10614141000415/21/{str(dpp_id).replace('-', '')[:12]}"
    )
    qr_service.generate_qr_code.return_value = b"legacy-carrier-bytes"

    monkeypatch.setattr(qr_router, "DPPService", lambda _db: dpp_service)
    monkeypatch.setattr(qr_router, "QRCodeService", lambda: qr_service)
    monkeypatch.setattr(qr_router, "require_access", AsyncMock(return_value=None))

    response = await qr_router.generate_carrier(
        dpp_id=dpp_id,
        request=CarrierRequest(
            format=CarrierFormat.GS1_QR,
            output_type=CarrierOutputType.PNG,
            include_text=False,
        ),
        db=AsyncMock(),
        tenant=tenant,
    )

    expected_serial = str(dpp_id).replace("-", "")[:12]
    qr_service.extract_gtin_from_asset_ids.assert_called_once_with(
        {"manufacturerPartId": "PART-001"}
    )
    qr_service.build_gs1_digital_link.assert_called_once_with("10614141000415", expected_serial)
    assert response.status_code == 200
    assert response.media_type == "image/png"
    assert response.body == b"legacy-carrier-bytes"


@pytest.mark.asyncio
async def test_get_gs1_digital_link_legacy_reports_pseudo_gtin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dpp_id = uuid4()
    dpp = _published_dpp(
        dpp_id,
        asset_ids={"manufacturerPartId": "PART-XYZ", "serialNumber": "SER-001"},
    )
    tenant = _tenant_context()

    dpp_service = MagicMock()
    dpp_service.get_dpp = AsyncMock(return_value=dpp)
    dpp_service.is_resource_shared_with_user = AsyncMock(return_value=False)

    qr_service = MagicMock()
    qr_service.extract_gtin_from_asset_ids.return_value = ("10614141000415", "SER-001", True)
    qr_service.build_gs1_digital_link.return_value = (
        "https://id.gs1.org/01/10614141000415/21/SER-001"
    )

    monkeypatch.setattr(qr_router, "DPPService", lambda _db: dpp_service)
    monkeypatch.setattr(qr_router, "QRCodeService", lambda: qr_service)
    monkeypatch.setattr(qr_router, "require_access", AsyncMock(return_value=None))

    response = await qr_router.get_gs1_digital_link(
        dpp_id=dpp_id,
        db=AsyncMock(),
        tenant=tenant,
    )

    assert str(response.dpp_id) == str(dpp_id)
    assert response.gtin == "10614141000415"
    assert response.serial == "SER-001"
    assert response.digital_link == "https://id.gs1.org/01/10614141000415/21/SER-001"
    assert response.resolver_url == "https://id.gs1.org"
    assert response.is_pseudo_gtin is True
