"""Regression tests for template provenance propagation across DPP revision paths."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db.models import DPPStatus, RevisionState
from app.modules.dpps.router import list_revisions
from app.modules.dpps.service import DPPService


def _session_mock() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


class TestProvenancePropagation:
    @pytest.mark.asyncio()
    async def test_create_dpp_from_environment_sets_empty_template_provenance(self) -> None:
        session = _session_mock()
        service = DPPService.__new__(DPPService)
        service._session = session
        service._settings = SimpleNamespace(global_asset_id_base_uri_default="")
        service._ensure_user_exists = AsyncMock()
        service._calculate_digest = MagicMock(return_value="digest")

        with (
            patch("app.modules.dpps.service.SettingsService") as settings_cls,
            patch("app.modules.dpps.service.QRCodeService") as qr_cls,
        ):
            settings_cls.return_value.get_setting = AsyncMock(return_value=None)
            qr_cls.return_value.build_dpp_url.return_value = "https://example.com/dpp/123"
            await service.create_dpp_from_environment(
                tenant_id=uuid4(),
                tenant_slug="tenant-a",
                owner_subject="owner-sub",
                asset_ids={"manufacturerPartId": "PART-1"},
                aas_env={"submodels": []},
            )

        revision = session.add.call_args_list[-1].args[0]
        assert revision.template_provenance == {}

    @pytest.mark.asyncio()
    async def test_update_submodel_defaults_provenance_to_empty_dict(self) -> None:
        session = _session_mock()
        service = DPPService.__new__(DPPService)
        service._session = session
        service.get_latest_revision = AsyncMock(
            return_value=SimpleNamespace(
                revision_no=3,
                aas_env_json={"submodels": []},
                template_provenance=None,
            )
        )
        service.get_dpp = AsyncMock(return_value=SimpleNamespace(asset_ids={"manufacturerPartId": "P-1"}))
        service._is_legacy_environment = MagicMock(return_value=False)
        service._template_service = SimpleNamespace(
            get_template=AsyncMock(return_value=SimpleNamespace(template_key="digital-nameplate"))
        )
        service._basyx_builder = SimpleNamespace(
            update_submodel_environment=MagicMock(return_value={"submodels": []})
        )
        service._calculate_digest = MagicMock(return_value="digest")
        service._cleanup_old_draft_revisions = AsyncMock(return_value=0)

        revision = await service.update_submodel(
            dpp_id=uuid4(),
            tenant_id=uuid4(),
            template_key="digital-nameplate",
            submodel_data={},
            updated_by_subject="owner-sub",
        )

        assert revision.template_provenance == {}
        added_revision = session.add.call_args_list[-1].args[0]
        assert added_revision.template_provenance == {}

    @pytest.mark.asyncio()
    async def test_update_submodel_preserves_existing_provenance(self) -> None:
        session = _session_mock()
        service = DPPService.__new__(DPPService)
        service._session = session
        existing = {"digital-nameplate": {"idta_version": "3.0.1"}}
        service.get_latest_revision = AsyncMock(
            return_value=SimpleNamespace(
                revision_no=7,
                aas_env_json={"submodels": []},
                template_provenance=existing,
            )
        )
        service.get_dpp = AsyncMock(return_value=SimpleNamespace(asset_ids={"manufacturerPartId": "P-2"}))
        service._is_legacy_environment = MagicMock(return_value=False)
        service._template_service = SimpleNamespace(
            get_template=AsyncMock(return_value=SimpleNamespace(template_key="digital-nameplate"))
        )
        service._basyx_builder = SimpleNamespace(
            update_submodel_environment=MagicMock(return_value={"submodels": []})
        )
        service._calculate_digest = MagicMock(return_value="digest")
        service._cleanup_old_draft_revisions = AsyncMock(return_value=0)

        revision = await service.update_submodel(
            dpp_id=uuid4(),
            tenant_id=uuid4(),
            template_key="digital-nameplate",
            submodel_data={},
            updated_by_subject="owner-sub",
        )

        assert revision.template_provenance == existing
        added_revision = session.add.call_args_list[-1].args[0]
        assert added_revision.template_provenance == existing

    @pytest.mark.asyncio()
    async def test_rebuild_from_templates_defaults_provenance_to_empty_dict(self) -> None:
        session = _session_mock()
        service = DPPService.__new__(DPPService)
        service._session = session
        service.get_latest_revision = AsyncMock(
            return_value=SimpleNamespace(
                revision_no=2,
                aas_env_json={"submodels": []},
                template_provenance=None,
            )
        )
        service._is_legacy_environment = MagicMock(return_value=False)
        service._basyx_builder = SimpleNamespace(
            rebuild_environment_from_templates=MagicMock(return_value=({"submodels": []}, True))
        )
        service._calculate_digest = MagicMock(return_value="digest")
        service._cleanup_old_draft_revisions = AsyncMock(return_value=0)

        dpp = SimpleNamespace(id=uuid4(), tenant_id=uuid4(), asset_ids={"manufacturerPartId": "P-3"})
        updated = await service._rebuild_dpp_from_templates(dpp=dpp, templates=[], updated_by_subject="owner")

        assert updated is True
        added_revision = session.add.call_args_list[-1].args[0]
        assert added_revision.template_provenance == {}

    @pytest.mark.asyncio()
    async def test_publish_new_revision_defaults_provenance_to_empty_dict(self) -> None:
        session = _session_mock()
        service = DPPService(session)
        service._settings = SimpleNamespace(compliance_check_on_publish=False)
        service._sign_digest = MagicMock(return_value="signed-jws")

        dpp = SimpleNamespace(
            id=uuid4(),
            tenant_id=uuid4(),
            status=DPPStatus.DRAFT,
            current_published_revision_id=None,
        )
        latest_revision = SimpleNamespace(
            id=uuid4(),
            revision_no=5,
            state=RevisionState.PUBLISHED,
            digest_sha256="digest",
            aas_env_json={"submodels": []},
            template_provenance=None,
        )
        service.get_dpp = AsyncMock(return_value=dpp)
        service.get_latest_revision = AsyncMock(return_value=latest_revision)

        await service.publish_dpp(dpp.id, dpp.tenant_id, "owner")

        added_revision = session.add.call_args_list[-1].args[0]
        assert added_revision.template_provenance == {}
        assert dpp.status == DPPStatus.PUBLISHED


class TestRevisionRouterResponse:
    @pytest.mark.asyncio()
    async def test_list_revisions_serializes_template_provenance(self) -> None:
        revision = SimpleNamespace(
            id=uuid4(),
            revision_no=1,
            state=RevisionState.DRAFT,
            digest_sha256="digest",
            created_by_subject="owner-sub",
            created_at=datetime.now(UTC),
            template_provenance={"digital-nameplate": {"idta_version": "3.0.1"}},
        )
        dpp = SimpleNamespace(owner_subject="owner-sub", revisions=[revision])
        service = SimpleNamespace(get_dpp=AsyncMock(return_value=dpp))
        tenant = SimpleNamespace(
            tenant_id=uuid4(),
            user=SimpleNamespace(sub="owner-sub"),
            is_tenant_admin=False,
        )

        with patch("app.modules.dpps.router.DPPService", return_value=service):
            payload = await list_revisions(dpp_id=uuid4(), db=AsyncMock(), tenant=tenant)

        assert len(payload) == 1
        assert payload[0].template_provenance == {"digital-nameplate": {"idta_version": "3.0.1"}}
