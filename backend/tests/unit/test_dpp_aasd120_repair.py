"""Unit tests for AASd-120 auto-heal and repair flows."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db.models import DPPStatus
from app.modules.aas.sanitization import SanitizationStats
from app.modules.dpps.service import DPPService


def _session_mock() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


class TestAASd120Autofix:
    @pytest.mark.asyncio()
    async def test_update_submodel_retries_with_sanitized_env(self) -> None:
        session = _session_mock()
        service = DPPService.__new__(DPPService)
        service._session = session
        service.get_latest_revision = AsyncMock(
            return_value=SimpleNamespace(
                revision_no=4,
                aas_env_json={
                    "assetAdministrationShells": [],
                    "submodels": [],
                    "conceptDescriptions": [],
                },
                template_provenance={"carbon-footprint": {"idta_version": "1.0.1"}},
            )
        )
        service.get_dpp = AsyncMock(
            return_value=SimpleNamespace(
                asset_ids={"manufacturerPartId": "X"}, status=DPPStatus.DRAFT
            )
        )
        service._is_legacy_environment = MagicMock(return_value=False)
        service._template_service = SimpleNamespace(
            get_template=AsyncMock(return_value=SimpleNamespace(template_key="carbon-footprint"))
        )
        service._basyx_builder = SimpleNamespace(
            update_submodel_environment=MagicMock(
                side_effect=[
                    ValueError("Constraint AASd-120"),
                    {"assetAdministrationShells": [], "submodels": [], "conceptDescriptions": []},
                ]
            )
        )
        service._calculate_digest = MagicMock(return_value="digest")
        service._cleanup_old_draft_revisions = AsyncMock(return_value=0)

        sanitized_env = {
            "assetAdministrationShells": [],
            "submodels": [],
            "conceptDescriptions": [],
        }
        with patch(
            "app.modules.dpps.service.sanitize_submodel_list_item_id_shorts",
            return_value=(
                sanitized_env,
                SanitizationStats(lists_scanned=2, items_scanned=3, idshort_removed=1),
            ),
        ) as sanitize_mock:
            revision = await service.update_submodel(
                dpp_id=uuid4(),
                tenant_id=uuid4(),
                template_key="carbon-footprint",
                submodel_data={},
                updated_by_subject="owner",
                rebuild_from_template=True,
            )

        assert revision.revision_no == 5
        assert sanitize_mock.call_count == 1
        assert service._basyx_builder.update_submodel_environment.call_count == 2
        second_call_kwargs = service._basyx_builder.update_submodel_environment.call_args_list[
            1
        ].kwargs
        assert second_call_kwargs["aas_env_json"] == sanitized_env
        added_revision = session.add.call_args_list[-1].args[0]
        assert added_revision.template_provenance == {"carbon-footprint": {"idta_version": "1.0.1"}}

    @pytest.mark.asyncio()
    async def test_update_submodel_non_aasd120_error_does_not_retry(self) -> None:
        session = _session_mock()
        service = DPPService.__new__(DPPService)
        service._session = session
        service.get_latest_revision = AsyncMock(
            return_value=SimpleNamespace(
                revision_no=1,
                aas_env_json={
                    "assetAdministrationShells": [],
                    "submodels": [],
                    "conceptDescriptions": [],
                },
                template_provenance={},
            )
        )
        service.get_dpp = AsyncMock(
            return_value=SimpleNamespace(
                asset_ids={"manufacturerPartId": "X"}, status=DPPStatus.DRAFT
            )
        )
        service._is_legacy_environment = MagicMock(return_value=False)
        service._template_service = SimpleNamespace(
            get_template=AsyncMock(return_value=SimpleNamespace(template_key="digital-nameplate"))
        )
        service._basyx_builder = SimpleNamespace(
            update_submodel_environment=MagicMock(side_effect=RuntimeError("connection reset"))
        )
        service._calculate_digest = MagicMock(return_value="digest")
        service._cleanup_old_draft_revisions = AsyncMock(return_value=0)

        with (
            patch(
                "app.modules.dpps.service.sanitize_submodel_list_item_id_shorts"
            ) as sanitize_mock,
            pytest.raises(ValueError, match="BaSyx update failed: connection reset"),
        ):
            await service.update_submodel(
                dpp_id=uuid4(),
                tenant_id=uuid4(),
                template_key="digital-nameplate",
                submodel_data={},
                updated_by_subject="owner",
            )

        assert sanitize_mock.call_count == 0
        assert service._basyx_builder.update_submodel_environment.call_count == 1


class TestRepairInvalidLists:
    @pytest.mark.asyncio()
    async def test_repair_creates_new_draft_revision_without_mutating_source(self) -> None:
        session = _session_mock()
        dpp_id = uuid4()
        tenant_id = uuid4()
        dpp = SimpleNamespace(
            id=dpp_id,
            tenant_id=tenant_id,
            status=DPPStatus.PUBLISHED,
            updated_at=datetime.now(UTC),
        )
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = [dpp]
        session.execute = AsyncMock(return_value=execute_result)

        current_env = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "id": "urn:sm:1",
                    "modelType": "Submodel",
                    "submodelElements": [
                        {
                            "idShort": "Codes",
                            "modelType": "SubmodelElementList",
                            "value": [
                                {
                                    "idShort": "generated_submodel_list_hack_1",
                                    "modelType": "Property",
                                    "valueType": "xs:string",
                                    "value": "A",
                                }
                            ],
                        }
                    ],
                }
            ],
            "conceptDescriptions": [],
        }
        current_revision = SimpleNamespace(
            revision_no=2,
            aas_env_json=current_env,
            template_provenance={"carbon-footprint": {"idta_version": "1.0.1"}},
        )

        service = DPPService.__new__(DPPService)
        service._session = session
        service.get_latest_revision = AsyncMock(return_value=current_revision)
        service._basyx_builder = SimpleNamespace(
            _load_environment=MagicMock(side_effect=ValueError("Constraint AASd-120"))  # noqa: SLF001
        )
        service._calculate_digest = MagicMock(return_value="digest")
        service._cleanup_old_draft_revisions = AsyncMock(return_value=0)

        sanitized_env = {
            "assetAdministrationShells": [],
            "submodels": [],
            "conceptDescriptions": [],
        }
        with patch(
            "app.modules.dpps.service.sanitize_submodel_list_item_id_shorts",
            return_value=(
                sanitized_env,
                SanitizationStats(lists_scanned=1, items_scanned=1, idshort_removed=1),
            ),
        ):
            summary = await service.repair_invalid_list_item_id_shorts(
                tenant_id=tenant_id,
                updated_by_subject="tenant-admin",
                dry_run=False,
            )

        assert summary["repaired"] == 1
        assert summary["skipped"] == 0
        assert current_revision.aas_env_json is current_env
        added_revision = session.add.call_args_list[-1].args[0]
        assert added_revision.revision_no == 3
        assert added_revision.aas_env_json == sanitized_env
        assert dpp.status == DPPStatus.PUBLISHED

    @pytest.mark.asyncio()
    async def test_repair_dry_run_reports_without_writing_revision(self) -> None:
        session = _session_mock()
        dpp = SimpleNamespace(
            id=uuid4(),
            tenant_id=uuid4(),
            status=DPPStatus.DRAFT,
            updated_at=datetime.now(UTC),
        )
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = [dpp]
        session.execute = AsyncMock(return_value=execute_result)

        service = DPPService.__new__(DPPService)
        service._session = session
        service.get_latest_revision = AsyncMock(
            return_value=SimpleNamespace(
                revision_no=1,
                aas_env_json={
                    "assetAdministrationShells": [],
                    "submodels": [],
                    "conceptDescriptions": [],
                },
                template_provenance={},
            )
        )
        service._basyx_builder = SimpleNamespace(
            _load_environment=MagicMock(side_effect=ValueError("Constraint AASd-120"))  # noqa: SLF001
        )
        service._calculate_digest = MagicMock(return_value="digest")
        service._cleanup_old_draft_revisions = AsyncMock(return_value=0)

        with patch(
            "app.modules.dpps.service.sanitize_submodel_list_item_id_shorts",
            return_value=(
                {"assetAdministrationShells": [], "submodels": [], "conceptDescriptions": []},
                SanitizationStats(lists_scanned=1, items_scanned=1, idshort_removed=1),
            ),
        ):
            summary = await service.repair_invalid_list_item_id_shorts(
                tenant_id=dpp.tenant_id,
                updated_by_subject="tenant-admin",
                dry_run=True,
            )

        assert summary["repaired"] == 1
        assert session.add.call_count == 0
