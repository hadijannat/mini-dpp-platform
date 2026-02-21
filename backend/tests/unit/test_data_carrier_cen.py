"""Unit tests for CEN data-carrier preflight behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.db.models import DataCarrierStatus as DataCarrierStatusDB
from app.db.models import DataCarrierType as DataCarrierTypeDB
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


@pytest.mark.asyncio
async def test_qa_report_detects_qr_layout_anomalies() -> None:
    service = DataCarrierService(AsyncMock())
    carrier = SimpleNamespace(
        id=uuid4(),
        encoded_uri="https://example.com/carrier",
        status=DataCarrierStatusDB.ACTIVE,
        carrier_type=DataCarrierTypeDB.QR,
        layout_profile={"error_correction": "X", "quiet_zone_modules": 20},
    )
    service.get_carrier = AsyncMock(return_value=carrier)  # type: ignore[method-assign]

    report = await service.build_qa_report(carrier_id=carrier.id, tenant_id=uuid4())
    checks = {check.check_type: check for check in report.checks}

    assert checks["qr_error_correction"].passed is False
    assert checks["qr_error_correction"].severity == "error"
    assert checks["qr_quiet_zone"].passed is False
    assert checks["qr_quiet_zone"].severity == "warning"


@pytest.mark.asyncio
async def test_qa_report_flags_datamatrix_runtime_unavailable() -> None:
    service = DataCarrierService(AsyncMock())
    carrier = SimpleNamespace(
        id=uuid4(),
        encoded_uri="https://example.com/carrier",
        status=DataCarrierStatusDB.ACTIVE,
        carrier_type=DataCarrierTypeDB.DATAMATRIX,
        layout_profile={},
    )
    service.get_carrier = AsyncMock(return_value=carrier)  # type: ignore[method-assign]
    service._datamatrix_renderer.is_available = lambda: False

    report = await service.build_qa_report(carrier_id=carrier.id, tenant_id=uuid4())
    checks = {check.check_type: check for check in report.checks}

    assert checks["datamatrix_runtime"].passed is False
    assert checks["datamatrix_runtime"].severity == "warning"


@pytest.mark.asyncio
async def test_qa_report_flags_nfc_capacity_overflow() -> None:
    service = DataCarrierService(AsyncMock())
    carrier = SimpleNamespace(
        id=uuid4(),
        encoded_uri="https://example.com/" + ("x" * 120),
        status=DataCarrierStatusDB.ACTIVE,
        carrier_type=DataCarrierTypeDB.NFC,
        layout_profile={"nfc_memory_bytes": 24},
    )
    service.get_carrier = AsyncMock(return_value=carrier)  # type: ignore[method-assign]

    report = await service.build_qa_report(carrier_id=carrier.id, tenant_id=uuid4())
    checks = {check.check_type: check for check in report.checks}

    assert checks["nfc_capacity"].passed is False
    assert checks["nfc_capacity"].severity == "error"
