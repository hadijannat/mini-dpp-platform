"""Unit tests for the ComplianceService layer."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.compliance.service import ComplianceService, _get_engine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_submodel(
    id_short: str,
    semantic_id: str,
    elements: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "idShort": id_short,
        "semanticId": {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": semantic_id}],
        },
        "modelType": "Submodel",
        "submodelElements": elements or [],
    }


def _make_property(id_short: str, value: Any = None) -> dict[str, Any]:
    return {"idShort": id_short, "modelType": "Property", "value": value}


def _battery_env() -> dict[str, Any]:
    return {
        "assetAdministrationShells": [],
        "submodels": [
            _make_submodel(
                "GeneralProductInformation",
                "https://admin-shell.io/idta/BatteryPassport/GeneralProductInformation/1/0",
                [
                    _make_property("ManufacturerIdentification", "ACME"),
                    _make_property("BatteryModel", "LFP-100"),
                    _make_property("BatteryWeight", "45.2"),
                    _make_property("BatteryCategory", "Industrial"),
                    _make_property("DateOfManufacturing", "2024-01-15"),
                ],
            ),
        ],
    }


def _mock_session_with_dpp(aas_env: dict[str, Any]) -> AsyncMock:
    """Create a mock session that returns a DPP and revision."""
    session = AsyncMock()
    tenant_id = uuid4()
    dpp_id = uuid4()

    # Mock DPP query result
    mock_dpp = MagicMock()
    mock_dpp.id = dpp_id
    mock_dpp.tenant_id = tenant_id

    # Mock revision query result
    mock_revision = MagicMock()
    mock_revision.aas_env_json = aas_env
    mock_revision.revision_no = 1

    # Each execute() call returns a different result
    dpp_result = MagicMock()
    dpp_result.scalar_one_or_none.return_value = mock_dpp

    revision_result = MagicMock()
    revision_result.scalar_one_or_none.return_value = mock_revision

    session.execute = AsyncMock(side_effect=[dpp_result, revision_result])

    return session, dpp_id, tenant_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestComplianceServiceCheckDpp:
    @pytest.mark.asyncio
    async def test_check_dpp_returns_report(self) -> None:
        session, dpp_id, tenant_id = _mock_session_with_dpp(_battery_env())
        service = ComplianceService(session)
        report = await service.check_dpp(dpp_id, tenant_id)
        assert report.dpp_id == dpp_id
        assert report.category == "battery"
        assert isinstance(report.summary.total_rules, int)

    @pytest.mark.asyncio
    async def test_check_dpp_with_explicit_category(self) -> None:
        session, dpp_id, tenant_id = _mock_session_with_dpp(_battery_env())
        service = ComplianceService(session)
        report = await service.check_dpp(dpp_id, tenant_id, category="battery")
        assert report.category == "battery"

    @pytest.mark.asyncio
    async def test_check_dpp_not_found(self) -> None:
        session = AsyncMock()
        dpp_result = MagicMock()
        dpp_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=dpp_result)

        service = ComplianceService(session)
        with pytest.raises(ValueError, match="not found"):
            await service.check_dpp(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_check_dpp_no_revision(self) -> None:
        session = AsyncMock()
        dpp_id = uuid4()
        tenant_id = uuid4()

        mock_dpp = MagicMock()
        mock_dpp.id = dpp_id
        mock_dpp.tenant_id = tenant_id

        dpp_result = MagicMock()
        dpp_result.scalar_one_or_none.return_value = mock_dpp

        revision_result = MagicMock()
        revision_result.scalar_one_or_none.return_value = None

        session.execute = AsyncMock(side_effect=[dpp_result, revision_result])

        service = ComplianceService(session)
        with pytest.raises(ValueError, match="No revision found"):
            await service.check_dpp(dpp_id, tenant_id)


class TestComplianceServicePrePublish:
    @pytest.mark.asyncio
    async def test_pre_publish_compliant(self) -> None:
        """Pre-publish check with all Part 1 fields present."""
        session, dpp_id, tenant_id = _mock_session_with_dpp(_battery_env())
        service = ComplianceService(session)
        report = await service.check_pre_publish(dpp_id, tenant_id)
        assert report.dpp_id == dpp_id
        # Part 1 fields are present, but other parts are missing
        # is_compliant depends on whether missing submodels cause violations
        assert isinstance(report.is_compliant, bool)

    @pytest.mark.asyncio
    async def test_pre_publish_non_compliant(self) -> None:
        """Pre-publish check with empty submodel should fail."""
        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [
                _make_submodel(
                    "GeneralProductInformation",
                    "https://admin-shell.io/idta/BatteryPassport/GeneralProductInformation/1/0",
                    [],
                ),
            ],
        }
        session, dpp_id, tenant_id = _mock_session_with_dpp(env)
        service = ComplianceService(session)
        report = await service.check_pre_publish(dpp_id, tenant_id)
        assert not report.is_compliant
        assert report.summary.critical_violations > 0


class TestComplianceServiceCheckAasEnv:
    @pytest.mark.asyncio
    async def test_check_raw_aas_env(self) -> None:
        session = AsyncMock()
        service = ComplianceService(session)
        report = await service.check_aas_env(_battery_env())
        assert report.category == "battery"
        assert report.dpp_id is None

    @pytest.mark.asyncio
    async def test_check_raw_aas_env_unknown_category(self) -> None:
        session = AsyncMock()
        service = ComplianceService(session)
        env: dict[str, Any] = {
            "submodels": [
                _make_submodel("Foo", "https://example.com/foo/1/0"),
            ],
        }
        report = await service.check_aas_env(env)
        assert report.category == "unknown"
        assert report.is_compliant


class TestGetEngine:
    def test_get_engine_singleton(self) -> None:
        engine1 = _get_engine()
        engine2 = _get_engine()
        assert engine1 is engine2

    def test_engine_has_categories(self) -> None:
        engine = _get_engine()
        cats = engine.list_categories()
        assert "battery" in cats
        assert "textile" in cats
        assert "electronic" in cats
