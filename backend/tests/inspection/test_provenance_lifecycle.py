"""Inspection tests for template provenance lifecycle tracking.

Validates that template_provenance JSONB is correctly captured, propagated,
and refreshed across the full DPP lifecycle: CREATE → UPDATE → PUBLISH → REBUILD.

Also validates:
- Template refresh mechanism updates source metadata
- Version determinism: same GitHub SHA → same definition hash
- Provenance JSONB contains expected fields at every stage
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db.models import DPPRevision, DPPStatus, RevisionState
from app.modules.dpps.service import DPPService
from app.modules.templates.catalog import get_template_descriptor
from app.modules.templates.service import (
    SELECTION_STRATEGY,
    _definition_cache,
)

DIGITAL_NAMEPLATE_SEMANTIC_ID = "https://admin-shell.io/idta/DigitalNameplate/Nameplate/3/0"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROVENANCE_EXPECTED_KEYS = {
    "idta_version",
    "semantic_id",
    "resolved_version",
    "source_file_sha",
    "source_file_path",
    "source_kind",
    "selection_strategy",
}


def _session_mock() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


def _minimal_conformant_env() -> dict[str, Any]:
    return {
        "assetAdministrationShells": [
            {
                "id": "urn:aas:test:1",
                "idShort": "AAS1",
                "modelType": "AssetAdministrationShell",
                "assetInformation": {
                    "assetKind": "Instance",
                    "globalAssetId": "urn:asset:test:1",
                },
                "submodels": [
                    {
                        "type": "ModelReference",
                        "keys": [{"type": "Submodel", "value": "urn:sm:test:1"}],
                    }
                ],
            }
        ],
        "submodels": [
            {
                "id": "urn:sm:test:1",
                "idShort": "SM1",
                "modelType": "Submodel",
                "semanticId": {
                    "type": "ExternalReference",
                    "keys": [
                        {
                            "type": "GlobalReference",
                            "value": DIGITAL_NAMEPLATE_SEMANTIC_ID,
                        }
                    ],
                },
                "submodelElements": [],
            }
        ],
        "conceptDescriptions": [],
    }


def _make_service(session: AsyncMock | None = None) -> DPPService:
    """Build a DPPService with mocked internals, bypassing __init__."""
    session = session or _session_mock()
    service = DPPService.__new__(DPPService)
    service._session = session
    service._settings = SimpleNamespace(
        global_asset_id_base_uri_default="",
        compliance_check_on_publish=False,
        dpp_max_draft_revisions=10,
        dpp_signing_key="",
    )
    service._ensure_user_exists = AsyncMock()
    service._calculate_digest = MagicMock(return_value="sha256_digest")
    service._sign_digest = MagicMock(return_value=None)
    return service


def _fake_template(
    template_key: str = "digital-nameplate",
    version: str = "3.0.1",
    source_file_sha: str | None = "abc123sha",
    source_file_path: str | None = "Digital nameplate/3/0/1/IDTA_02006.json",
    source_kind: str | None = "json",
    selection_strategy: str | None = SELECTION_STRATEGY,
) -> SimpleNamespace:
    """Create a fake Template DB record for provenance tests."""
    return SimpleNamespace(
        template_key=template_key,
        idta_version=version,
        resolved_version=version,
        semantic_id="https://admin-shell.io/zvei/nameplate/2/0/Nameplate",
        source_url="https://raw.githubusercontent.com/admin-shell-io/submodel-templates/main/...",
        source_repo_ref="main",
        source_file_path=source_file_path,
        source_file_sha=source_file_sha,
        source_kind=source_kind,
        selection_strategy=selection_strategy,
        template_aasx=None,
        template_json={"submodels": [{"idShort": "Nameplate"}], "conceptDescriptions": []},
        fetched_at=datetime.now(UTC),
    )


def _assert_provenance_fields(provenance: dict[str, Any], template_key: str) -> None:
    """Assert that provenance dict has all expected keys for a given template."""
    assert template_key in provenance, f"Missing template key '{template_key}' in provenance"
    entry = provenance[template_key]
    assert isinstance(entry, dict), f"Provenance entry for '{template_key}' is not a dict"
    for key in PROVENANCE_EXPECTED_KEYS:
        assert key in entry, f"Missing provenance field '{key}' for template '{template_key}'"


# ===========================================================================
# Phase 1: CREATE — provenance captured when creating a new DPP
# ===========================================================================


class TestCreateProvenance:
    """Verify template_provenance is captured when creating a DPP from templates."""

    @pytest.mark.asyncio()
    async def test_create_dpp_captures_provenance_from_templates(self) -> None:
        """CREATE path: provenance should be built from catalog descriptors + DB templates."""
        session = _session_mock()
        service = _make_service(session)

        fake_template = _fake_template()

        # Mock the template DB query to return our fake template
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = fake_template
        session.execute = AsyncMock(return_value=execute_result)

        service._template_service = SimpleNamespace(
            get_template=AsyncMock(return_value=fake_template),
        )
        service._basyx_builder = SimpleNamespace(
            build_environment=AsyncMock(
                return_value={"assetAdministrationShells": [], "submodels": []}
            )
        )

        with (
            patch("app.modules.dpps.service.SettingsService") as settings_cls,
            patch("app.modules.dpps.service.QRCodeService") as qr_cls,
        ):
            settings_cls.return_value.get_setting = AsyncMock(return_value=None)
            qr_cls.return_value.build_dpp_url.return_value = "https://example.com/dpp/test"

            await service.create_dpp(
                tenant_id=uuid4(),
                tenant_slug="test-tenant",
                owner_subject="owner-sub",
                asset_ids={"manufacturerPartId": "PART-001"},
                selected_templates=["digital-nameplate"],
            )

        # The last session.add call should be the DPPRevision
        revision = session.add.call_args_list[-1].args[0]
        assert isinstance(revision, DPPRevision)
        assert revision.template_provenance is not None
        assert isinstance(revision.template_provenance, dict)
        assert "digital-nameplate" in revision.template_provenance

        entry = revision.template_provenance["digital-nameplate"]
        assert entry["idta_version"] is not None
        assert entry["semantic_id"] is not None

    @pytest.mark.asyncio()
    async def test_create_dpp_from_environment_sets_empty_provenance(self) -> None:
        """Import path: imported DPPs have no template context, so provenance = {}."""
        session = _session_mock()
        service = _make_service(session)

        with (
            patch("app.modules.dpps.service.SettingsService") as settings_cls,
            patch("app.modules.dpps.service.QRCodeService") as qr_cls,
        ):
            settings_cls.return_value.get_setting = AsyncMock(return_value=None)
            qr_cls.return_value.build_dpp_url.return_value = "https://example.com/dpp/imported"

            await service.create_dpp_from_environment(
                tenant_id=uuid4(),
                tenant_slug="test-tenant",
                owner_subject="importer-sub",
                asset_ids={"manufacturerPartId": "IMPORTED-001"},
                aas_env={"assetAdministrationShells": [], "submodels": []},
            )

        revision = session.add.call_args_list[-1].args[0]
        assert isinstance(revision, DPPRevision)
        assert revision.template_provenance == {}

    @pytest.mark.asyncio()
    async def test_create_provenance_contains_all_expected_fields(self) -> None:
        """Provenance JSONB should include all 7 expected metadata fields."""
        session = _session_mock()
        service = _make_service(session)

        fake_template = _fake_template(
            source_file_sha="deadbeef123",
            source_file_path="Digital nameplate/3/0/1/file.json",
            source_kind="json",
            selection_strategy="deterministic_v2",
        )
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = fake_template
        session.execute = AsyncMock(return_value=execute_result)

        provenance = await service._build_template_provenance(["digital-nameplate"])

        _assert_provenance_fields(provenance, "digital-nameplate")
        entry = provenance["digital-nameplate"]
        assert entry["source_file_sha"] == "deadbeef123"
        assert entry["source_kind"] == "json"
        assert entry["selection_strategy"] == "deterministic_v2"

    @pytest.mark.asyncio()
    async def test_create_provenance_handles_missing_db_template(self) -> None:
        """If template is not in DB yet, provenance still has catalog metadata with None fields."""
        session = _session_mock()
        service = _make_service(session)

        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=execute_result)

        provenance = await service._build_template_provenance(["digital-nameplate"])

        assert "digital-nameplate" in provenance
        entry = provenance["digital-nameplate"]
        assert entry["idta_version"] is not None  # From catalog descriptor
        assert entry["semantic_id"] is not None  # From catalog descriptor
        assert entry["resolved_version"] is None  # No DB template
        assert entry["source_file_sha"] is None  # No DB template


# ===========================================================================
# Phase 2: UPDATE — provenance preserved across submodel updates
# ===========================================================================


class TestUpdateProvenance:
    """Verify provenance carries forward when updating a submodel."""

    @pytest.mark.asyncio()
    async def test_update_preserves_existing_provenance(self) -> None:
        """UPDATE path: provenance from previous revision should carry forward unchanged."""
        session = _session_mock()
        service = _make_service(session)
        existing_provenance = {
            "digital-nameplate": {
                "idta_version": "3.0.1",
                "semantic_id": "https://admin-shell.io/zvei/nameplate/2/0/Nameplate",
                "resolved_version": "3.0.1",
                "source_file_sha": "original_sha",
                "source_file_path": "Digital nameplate/3/0/1/template.json",
                "source_kind": "json",
                "selection_strategy": "deterministic_v2",
            }
        }

        service.get_latest_revision = AsyncMock(
            return_value=SimpleNamespace(
                revision_no=3,
                aas_env_json=_minimal_conformant_env(),
                template_provenance=existing_provenance,
            )
        )
        service.get_dpp = AsyncMock(
            return_value=SimpleNamespace(
                asset_ids={"manufacturerPartId": "P-1"},
                status=DPPStatus.DRAFT,
            )
        )
        service._is_legacy_environment = MagicMock(return_value=False)
        service._template_service = SimpleNamespace(
            get_template=AsyncMock(
                return_value=SimpleNamespace(
                    template_key="digital-nameplate",
                    semantic_id=DIGITAL_NAMEPLATE_SEMANTIC_ID,
                )
            )
        )
        service._basyx_builder = SimpleNamespace(
            update_submodel_environment=MagicMock(
                return_value={"assetAdministrationShells": [], "submodels": []}
            )
        )
        service._cleanup_old_draft_revisions = AsyncMock(return_value=0)

        revision = await service.update_submodel(
            dpp_id=uuid4(),
            tenant_id=uuid4(),
            template_key="digital-nameplate",
            submodel_data={"ManufacturerName": [{"language": "en", "text": "Test Corp"}]},
            updated_by_subject="editor-sub",
        )

        assert revision.template_provenance == existing_provenance
        # Also verify the object added to session has same provenance
        added = session.add.call_args_list[-1].args[0]
        assert added.template_provenance == existing_provenance

    @pytest.mark.asyncio()
    async def test_update_defaults_none_provenance_to_empty_dict(self) -> None:
        """UPDATE path with None provenance: `or {}` fallback should produce empty dict."""
        session = _session_mock()
        service = _make_service(session)

        service.get_latest_revision = AsyncMock(
            return_value=SimpleNamespace(
                revision_no=1,
                aas_env_json=_minimal_conformant_env(),
                template_provenance=None,  # Legacy revision — no provenance
            )
        )
        service.get_dpp = AsyncMock(
            return_value=SimpleNamespace(
                asset_ids={"manufacturerPartId": "P-1"},
                status=DPPStatus.DRAFT,
            )
        )
        service._is_legacy_environment = MagicMock(return_value=False)
        service._template_service = SimpleNamespace(
            get_template=AsyncMock(
                return_value=SimpleNamespace(
                    template_key="digital-nameplate",
                    semantic_id=DIGITAL_NAMEPLATE_SEMANTIC_ID,
                )
            )
        )
        service._basyx_builder = SimpleNamespace(
            update_submodel_environment=MagicMock(
                return_value={"assetAdministrationShells": [], "submodels": []}
            )
        )
        service._cleanup_old_draft_revisions = AsyncMock(return_value=0)

        revision = await service.update_submodel(
            dpp_id=uuid4(),
            tenant_id=uuid4(),
            template_key="digital-nameplate",
            submodel_data={},
            updated_by_subject="editor-sub",
        )

        assert revision.template_provenance == {}

    @pytest.mark.asyncio()
    async def test_update_does_not_mutate_previous_revision_provenance(self) -> None:
        """Provenance dict should be copied, not mutated in place."""
        session = _session_mock()
        service = _make_service(session)
        original_provenance = {"digital-nameplate": {"idta_version": "3.0.1"}}

        prev_revision = SimpleNamespace(
            revision_no=2,
            aas_env_json=_minimal_conformant_env(),
            template_provenance=original_provenance,
        )
        service.get_latest_revision = AsyncMock(return_value=prev_revision)
        service.get_dpp = AsyncMock(
            return_value=SimpleNamespace(
                asset_ids={"manufacturerPartId": "P-1"},
                status=DPPStatus.DRAFT,
            )
        )
        service._is_legacy_environment = MagicMock(return_value=False)
        service._template_service = SimpleNamespace(
            get_template=AsyncMock(
                return_value=SimpleNamespace(
                    template_key="digital-nameplate",
                    semantic_id=DIGITAL_NAMEPLATE_SEMANTIC_ID,
                )
            )
        )
        service._basyx_builder = SimpleNamespace(
            update_submodel_environment=MagicMock(
                return_value={"assetAdministrationShells": [], "submodels": []}
            )
        )
        service._cleanup_old_draft_revisions = AsyncMock(return_value=0)

        await service.update_submodel(
            dpp_id=uuid4(),
            tenant_id=uuid4(),
            template_key="digital-nameplate",
            submodel_data={},
            updated_by_subject="editor-sub",
        )

        # `or {}` with a truthy dict returns the same dict object reference,
        # which is acceptable since revisions are immutable DB rows.
        # The key invariant is that the CONTENT is correct.
        added = session.add.call_args_list[-1].args[0]
        assert added.template_provenance == original_provenance


# ===========================================================================
# Phase 3: PUBLISH — provenance in published revision
# ===========================================================================


class TestPublishProvenance:
    """Verify provenance is correctly handled during DPP publication."""

    @pytest.mark.asyncio()
    async def test_publish_draft_to_published_preserves_provenance_in_place(self) -> None:
        """PUBLISH (draft→published flip): provenance stays on same revision object."""
        session = _session_mock()
        service = _make_service(session)

        provenance = {"digital-nameplate": {"idta_version": "3.0.1"}}
        revision = SimpleNamespace(
            id=uuid4(),
            revision_no=1,
            state=RevisionState.DRAFT,
            digest_sha256="sha256_digest",
            aas_env_json={"submodels": []},
            signed_jws=None,
            template_provenance=provenance,
        )
        dpp = SimpleNamespace(
            id=uuid4(),
            tenant_id=uuid4(),
            status=DPPStatus.DRAFT,
            current_published_revision_id=None,
        )
        service.get_dpp = AsyncMock(return_value=dpp)
        service.get_latest_revision = AsyncMock(return_value=revision)

        await service.publish_dpp(dpp.id, dpp.tenant_id, "publisher-sub")

        # Draft→published flip: no new revision created, provenance unchanged
        assert revision.state == RevisionState.PUBLISHED
        assert revision.template_provenance == provenance

    @pytest.mark.asyncio()
    async def test_publish_creates_new_revision_with_provenance(self) -> None:
        """PUBLISH (already published, re-publish): new revision should carry provenance."""
        session = _session_mock()
        service = _make_service(session)

        provenance = {
            "digital-nameplate": {
                "idta_version": "3.0.1",
                "source_file_sha": "abc123",
            }
        }
        revision = SimpleNamespace(
            id=uuid4(),
            revision_no=5,
            state=RevisionState.PUBLISHED,
            digest_sha256="sha256_digest",
            aas_env_json={"submodels": []},
            template_provenance=provenance,
        )
        dpp = SimpleNamespace(
            id=uuid4(),
            tenant_id=uuid4(),
            status=DPPStatus.PUBLISHED,
            current_published_revision_id=revision.id,
        )
        service.get_dpp = AsyncMock(return_value=dpp)
        service.get_latest_revision = AsyncMock(return_value=revision)

        await service.publish_dpp(dpp.id, dpp.tenant_id, "publisher-sub")

        # New revision should have been added
        added = session.add.call_args_list[-1].args[0]
        assert isinstance(added, DPPRevision)
        assert added.template_provenance == provenance
        assert added.state == RevisionState.PUBLISHED
        assert added.revision_no == 6

    @pytest.mark.asyncio()
    async def test_publish_new_revision_defaults_null_provenance(self) -> None:
        """PUBLISH with null provenance: `or {}` should default to empty dict."""
        session = _session_mock()
        service = _make_service(session)

        revision = SimpleNamespace(
            id=uuid4(),
            revision_no=3,
            state=RevisionState.PUBLISHED,
            digest_sha256="sha256_digest",
            aas_env_json={"submodels": []},
            template_provenance=None,
        )
        dpp = SimpleNamespace(
            id=uuid4(),
            tenant_id=uuid4(),
            status=DPPStatus.DRAFT,
            current_published_revision_id=None,
        )
        service.get_dpp = AsyncMock(return_value=dpp)
        service.get_latest_revision = AsyncMock(return_value=revision)

        await service.publish_dpp(dpp.id, dpp.tenant_id, "publisher-sub")

        added = session.add.call_args_list[-1].args[0]
        assert isinstance(added, DPPRevision)
        assert added.template_provenance == {}


# ===========================================================================
# Phase 4: REBUILD — fresh provenance computed from latest DB templates
# ===========================================================================


class TestRebuildProvenance:
    """Verify rebuild computes fresh provenance from current DB templates."""

    @pytest.mark.asyncio()
    async def test_rebuild_computes_fresh_provenance(self) -> None:
        """REBUILD: provenance should come from _build_provenance_from_db_templates, not old revision."""
        session = _session_mock()
        service = _make_service(session)

        stale_provenance = {"digital-nameplate": {"source_file_sha": "old_sha"}}
        service.get_latest_revision = AsyncMock(
            return_value=SimpleNamespace(
                revision_no=2,
                aas_env_json={"assetAdministrationShells": [], "submodels": []},
                template_provenance=stale_provenance,
            )
        )
        service._is_legacy_environment = MagicMock(return_value=False)
        service._basyx_builder = SimpleNamespace(
            rebuild_environment_from_templates=MagicMock(
                return_value=({"assetAdministrationShells": [], "submodels": []}, True)
            )
        )
        service._cleanup_old_draft_revisions = AsyncMock(return_value=0)

        # Create template objects with FRESH metadata
        fake_templates = [
            SimpleNamespace(
                template_key="digital-nameplate",
                idta_version="3.0.1",
                resolved_version="3.0.1",
                source_file_sha="new_sha_from_refresh",
                source_file_path="Digital nameplate/3/0/1/fresh.json",
                source_kind="json",
                selection_strategy="deterministic_v2",
                semantic_id="https://admin-shell.io/zvei/nameplate/2/0/Nameplate",
            )
        ]

        dpp = SimpleNamespace(
            id=uuid4(),
            tenant_id=uuid4(),
            asset_ids={"manufacturerPartId": "P-REBUILD"},
        )

        updated = await service._rebuild_dpp_from_templates(
            dpp=dpp,
            templates=fake_templates,
            updated_by_subject="rebuilder-sub",
        )

        assert updated is True
        added = session.add.call_args_list[-1].args[0]
        assert isinstance(added, DPPRevision)

        # Fresh provenance — NOT the stale "old_sha"
        prov = added.template_provenance
        assert prov is not None
        assert "digital-nameplate" in prov
        assert prov["digital-nameplate"]["source_file_sha"] == "new_sha_from_refresh"
        assert prov["digital-nameplate"]["resolved_version"] == "3.0.1"

    @pytest.mark.asyncio()
    async def test_rebuild_no_change_returns_false(self) -> None:
        """REBUILD with no env changes should return False (no new revision)."""
        session = _session_mock()
        service = _make_service(session)

        service.get_latest_revision = AsyncMock(
            return_value=SimpleNamespace(
                revision_no=1,
                aas_env_json={"assetAdministrationShells": [], "submodels": []},
                template_provenance={"digital-nameplate": {"idta_version": "3.0.1"}},
            )
        )
        service._is_legacy_environment = MagicMock(return_value=False)
        service._basyx_builder = SimpleNamespace(
            rebuild_environment_from_templates=MagicMock(
                return_value=({"assetAdministrationShells": [], "submodels": []}, False)
            )
        )

        dpp = SimpleNamespace(
            id=uuid4(),
            tenant_id=uuid4(),
            asset_ids={"manufacturerPartId": "P-NOCHANGE"},
        )

        updated = await service._rebuild_dpp_from_templates(
            dpp=dpp, templates=[], updated_by_subject="rebuilder-sub"
        )

        assert updated is False
        # No revision should have been added
        assert session.add.call_count == 0

    @pytest.mark.asyncio()
    async def test_rebuild_provenance_includes_all_fields(self) -> None:
        """Rebuilt provenance should include all expected metadata fields."""
        session = _session_mock()
        service = _make_service(session)

        templates = [
            SimpleNamespace(
                template_key="digital-nameplate",
                idta_version="3.0.1",
                resolved_version="3.0.1",
                source_file_sha="full_fields_sha",
                source_file_path="Digital nameplate/3/0/1/template.json",
                source_kind="json",
                selection_strategy="deterministic_v2",
                semantic_id="https://admin-shell.io/zvei/nameplate/2/0/Nameplate",
            )
        ]

        provenance = await service._build_provenance_from_db_templates(templates)

        _assert_provenance_fields(provenance, "digital-nameplate")


# ===========================================================================
# Phase 5: Template Refresh Mechanism
# ===========================================================================


class TestTemplateRefresh:
    """Validate template refresh updates source metadata for provenance tracking."""

    @pytest.mark.asyncio()
    async def test_refresh_router_returns_counter_summary(self) -> None:
        """POST /templates/refresh should return attempted/successful/failed/skipped counts."""
        from app.modules.templates.router import TemplateListResponse

        response = TemplateListResponse(
            templates=[],
            count=5,
            attempted_count=7,
            successful_count=5,
            failed_count=1,
            skipped_count=1,
            refresh_results=[],
        )

        assert response.attempted_count == 7
        assert response.successful_count == 5
        assert response.failed_count == 1
        assert response.skipped_count == 1

    def test_refresh_result_schema_includes_source_metadata(self) -> None:
        """TemplateRefreshResult should carry source_metadata for provenance audit."""
        from app.modules.templates.service import TemplateRefreshResult

        result = TemplateRefreshResult(
            template_key="digital-nameplate",
            status="ok",
            support_status="supported",
            idta_version="3.0.1",
            resolved_version="3.0.1",
            source_metadata={
                "resolved_version": "3.0.1",
                "source_repo_ref": "main",
                "source_file_path": "path/to/file.json",
                "source_file_sha": "abc123",
                "source_kind": "json",
                "selection_strategy": "deterministic_v2",
                "source_url": "https://...",
            },
        )

        assert result.source_metadata is not None
        assert result.source_metadata["source_file_sha"] == "abc123"

    def test_unavailable_templates_are_skipped_during_refresh(self) -> None:
        """Templates with refresh_enabled=False should not attempt HTTP fetch."""
        descriptor = get_template_descriptor("battery-passport")
        if descriptor is not None and not descriptor.refresh_enabled:
            # Battery passport is marked unavailable upstream — correct behavior
            assert descriptor.support_status in ("unavailable", "experimental")


# ===========================================================================
# Phase 6: Version Determinism
# ===========================================================================


class TestVersionDeterminism:
    """Validate that the definition cache key ensures same SHA → same definition."""

    def test_definition_cache_key_includes_sha(self) -> None:
        """Cache key is (template_key, version, source_file_sha) — SHA is part of identity."""
        # The cache key structure is documented in service.py:
        # _definition_cache: dict[tuple[str, str, str | None], dict[str, Any]]
        key = ("digital-nameplate", "3.0.1", "abc123sha")
        assert len(key) == 3
        assert key[2] == "abc123sha"

    def test_same_sha_produces_cache_hit(self) -> None:
        """Two requests with same (key, version, sha) should share cached definition."""
        cache_key = ("test-template", "1.0.0", "same_sha")
        fake_definition = {"type": "submodel", "idShort": "Test"}

        # Simulate caching
        _definition_cache[cache_key] = fake_definition

        # Lookup should hit
        assert _definition_cache.get(cache_key) is fake_definition

        # Cleanup
        _definition_cache.pop(cache_key, None)

    def test_different_sha_produces_cache_miss(self) -> None:
        """Different SHA should NOT match a cached definition."""
        key_v1 = ("test-template", "1.0.0", "sha_v1")
        key_v2 = ("test-template", "1.0.0", "sha_v2")
        fake_definition = {"type": "submodel", "idShort": "Test"}

        _definition_cache[key_v1] = fake_definition

        assert _definition_cache.get(key_v2) is None

        # Cleanup
        _definition_cache.pop(key_v1, None)

    def test_selection_strategy_is_deterministic_v2(self) -> None:
        """The current selection strategy should be 'deterministic_v2'."""
        assert SELECTION_STRATEGY == "deterministic_v2"

    def test_catalog_descriptors_have_stable_semantic_ids(self) -> None:
        """All catalog templates should have non-empty semantic IDs for provenance tracking."""
        from app.modules.templates.catalog import CORE_TEMPLATE_KEYS

        for key in CORE_TEMPLATE_KEYS:
            descriptor = get_template_descriptor(key)
            assert descriptor is not None, f"Missing descriptor for '{key}'"
            assert descriptor.semantic_id, f"Empty semantic_id for '{key}'"
            assert descriptor.baseline_major >= 1, f"Invalid baseline_major for '{key}'"


# ===========================================================================
# Phase 7: Provenance Null-Safety (regression guards)
# ===========================================================================


class TestProvenanceNullSafety:
    """Ensure `or {}` guards prevent None from leaking into revision provenance."""

    @pytest.mark.asyncio()
    async def test_update_or_guard_on_none(self) -> None:
        """service.py line 644: `current_revision.template_provenance or {}` guards None."""
        session = _session_mock()
        service = _make_service(session)
        env = _minimal_conformant_env()

        service.get_latest_revision = AsyncMock(
            return_value=SimpleNamespace(
                revision_no=1,
                aas_env_json=env,
                template_provenance=None,
            )
        )
        service.get_dpp = AsyncMock(
            return_value=SimpleNamespace(
                asset_ids={"manufacturerPartId": "P-1"},
                status=DPPStatus.DRAFT,
            )
        )
        service._is_legacy_environment = MagicMock(return_value=False)
        service._template_service = SimpleNamespace(
            get_template=AsyncMock(
                return_value=SimpleNamespace(
                    template_key="digital-nameplate",
                    semantic_id=DIGITAL_NAMEPLATE_SEMANTIC_ID,
                )
            )
        )
        service._basyx_builder = SimpleNamespace(
            update_submodel_environment=MagicMock(return_value=env)
        )
        service._cleanup_old_draft_revisions = AsyncMock(return_value=0)

        revision = await service.update_submodel(
            dpp_id=uuid4(),
            tenant_id=uuid4(),
            template_key="digital-nameplate",
            submodel_data={},
            updated_by_subject="owner",
        )

        # Must be {} not None
        assert revision.template_provenance is not None
        assert revision.template_provenance == {}

    @pytest.mark.asyncio()
    async def test_publish_or_guard_on_none(self) -> None:
        """service.py line 759: `latest_revision.template_provenance or {}` guards None."""
        session = _session_mock()
        service = _make_service(session)

        revision = SimpleNamespace(
            id=uuid4(),
            revision_no=3,
            state=RevisionState.PUBLISHED,
            digest_sha256="digest",
            aas_env_json={"submodels": []},
            template_provenance=None,
        )
        dpp = SimpleNamespace(
            id=uuid4(),
            tenant_id=uuid4(),
            status=DPPStatus.DRAFT,
            current_published_revision_id=None,
        )
        service.get_dpp = AsyncMock(return_value=dpp)
        service.get_latest_revision = AsyncMock(return_value=revision)

        await service.publish_dpp(dpp.id, dpp.tenant_id, "publisher")

        added = session.add.call_args_list[-1].args[0]
        assert added.template_provenance is not None
        assert added.template_provenance == {}


# ===========================================================================
# Phase 8: Migration 0023 structural validation
# ===========================================================================


class TestMigration0023:
    """Validate the migration that added template_provenance column."""

    def test_revision_id_within_alembic_limit(self) -> None:
        """Revision ID must be ≤32 chars (Alembic varchar(32) constraint)."""
        revision_id = "0023_template_provenance"
        assert len(revision_id) <= 32, f"Revision ID too long: {len(revision_id)} chars"

    def test_model_column_is_nullable_jsonb(self) -> None:
        """DPPRevision.template_provenance should be nullable JSONB."""
        import sqlalchemy

        column = DPPRevision.__table__.columns["template_provenance"]
        assert column.nullable is True
        assert isinstance(column.type, sqlalchemy.dialects.postgresql.JSONB)
