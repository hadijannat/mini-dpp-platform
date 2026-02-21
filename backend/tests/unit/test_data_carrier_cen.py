"""Unit tests for CEN data-carrier preflight behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

from app.modules.data_carriers.schemas import (
    DataCarrierLayoutProfile,
    DataCarrierType,
    DataCarrierValidationRequest,
)
from app.modules.data_carriers.service import DataCarrierService


def test_preflight_reports_datamatrix_runtime_unavailable(monkeypatch) -> None:
    service = DataCarrierService(AsyncMock())
    monkeypatch.setattr(service._datamatrix_renderer, "is_available", lambda: False)

    response = service.validate_payload_preflight(
        request=DataCarrierValidationRequest(
            carrier_type=DataCarrierType.DATAMATRIX,
            payload="https://example.com/dpp/123",
        )
    )

    assert response.valid is False
    assert response.details.get("runtime_available") is False
    assert any("DataMatrix renderer unavailable" in warning for warning in response.warnings)


def test_preflight_enforces_nfc_memory_limit() -> None:
    service = DataCarrierService(AsyncMock())
    response = service.validate_payload_preflight(
        request=DataCarrierValidationRequest(
            carrier_type=DataCarrierType.NFC,
            payload="https://example.com/" + ("x" * 80),
            layout_profile=DataCarrierLayoutProfile(nfc_memory_bytes=32),
        )
    )
    assert response.valid is False
    assert any("exceeds configured memory" in warning for warning in response.warnings)


def test_preflight_returns_qr_profile_details() -> None:
    service = DataCarrierService(AsyncMock())
    response = service.validate_payload_preflight(
        request=DataCarrierValidationRequest(
            carrier_type=DataCarrierType.QR,
            payload="https://example.com/dpp/123",
            layout_profile=DataCarrierLayoutProfile(error_correction="Q", quiet_zone_modules=2),
        )
    )

    assert response.valid is True
    assert response.details["error_correction"] == "Q"
    assert response.details["quiet_zone_modules"] == 2
