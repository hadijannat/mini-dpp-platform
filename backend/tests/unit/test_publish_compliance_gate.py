"""Tests for the compliance pre-publish gate wired into DPPService.publish_dpp()."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.compliance.schemas import ComplianceReport, ComplianceSummary
from app.modules.dpps.service import DPPService


def _mock_dpp() -> MagicMock:
    dpp = MagicMock()
    dpp.id = uuid4()
    dpp.tenant_id = uuid4()
    dpp.status = MagicMock(value="draft")
    dpp.owner_subject = "test-subject"
    return dpp


def _mock_revision() -> MagicMock:
    rev = MagicMock()
    rev.revision_no = 1
    rev.state = MagicMock(value="draft")
    rev.digest_sha256 = "abc123"
    rev.signed_jws = None
    rev.aas_env_json = {"submodels": []}
    return rev


def _compliant_report() -> ComplianceReport:
    return ComplianceReport(
        category="battery",
        is_compliant=True,
        checked_at=datetime.now(tz=UTC),
        violations=[],
        summary=ComplianceSummary(
            total_rules=5,
            passed=5,
            critical_violations=0,
            warnings=0,
        ),
    )


def _non_compliant_report() -> ComplianceReport:
    return ComplianceReport(
        category="battery",
        is_compliant=False,
        checked_at=datetime.now(tz=UTC),
        violations=[],
        summary=ComplianceSummary(
            total_rules=5,
            passed=2,
            critical_violations=3,
            warnings=0,
        ),
    )


class TestPublishComplianceGate:
    @pytest.mark.asyncio
    async def test_publish_blocked_when_non_compliant(self) -> None:
        """publish_dpp raises ValueError when compliance gate rejects."""
        service = DPPService(AsyncMock())
        dpp = _mock_dpp()
        rev = _mock_revision()

        with (
            patch.object(service, "_settings") as mock_settings,
            patch.object(service, "get_dpp", return_value=dpp),
            patch.object(service, "get_latest_revision", return_value=rev),
            patch(
                "app.modules.dpps.service.ComplianceService"
            ) as MockComplianceSvc,
        ):
            mock_settings.compliance_check_on_publish = True
            mock_instance = MockComplianceSvc.return_value
            mock_instance.check_pre_publish = AsyncMock(
                return_value=_non_compliant_report()
            )

            with pytest.raises(ValueError, match="Publish blocked"):
                await service.publish_dpp(dpp.id, dpp.tenant_id, "user-sub")

    @pytest.mark.asyncio
    async def test_publish_proceeds_when_compliant(self) -> None:
        """publish_dpp continues normally when compliance check passes."""
        session = AsyncMock()
        service = DPPService(session)
        dpp = _mock_dpp()
        rev = _mock_revision()

        with (
            patch.object(service, "_settings") as mock_settings,
            patch.object(service, "get_dpp", return_value=dpp),
            patch.object(service, "get_latest_revision", return_value=rev),
            patch.object(service, "_sign_digest", return_value=None),
            patch(
                "app.modules.dpps.service.ComplianceService"
            ) as MockComplianceSvc,
        ):
            mock_settings.compliance_check_on_publish = True
            mock_instance = MockComplianceSvc.return_value
            mock_instance.check_pre_publish = AsyncMock(
                return_value=_compliant_report()
            )

            result = await service.publish_dpp(dpp.id, dpp.tenant_id, "user-sub")
            assert result is not None
            mock_instance.check_pre_publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publish_skips_gate_when_disabled(self) -> None:
        """publish_dpp skips compliance check when setting is off."""
        session = AsyncMock()
        service = DPPService(session)
        dpp = _mock_dpp()
        rev = _mock_revision()

        with (
            patch.object(service, "_settings") as mock_settings,
            patch.object(service, "get_dpp", return_value=dpp),
            patch.object(service, "get_latest_revision", return_value=rev),
            patch.object(service, "_sign_digest", return_value=None),
            patch(
                "app.modules.dpps.service.ComplianceService"
            ) as MockComplianceSvc,
        ):
            mock_settings.compliance_check_on_publish = False

            result = await service.publish_dpp(dpp.id, dpp.tenant_id, "user-sub")
            assert result is not None
            MockComplianceSvc.assert_not_called()
