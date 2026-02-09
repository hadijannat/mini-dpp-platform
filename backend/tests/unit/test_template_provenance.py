"""Tests for template provenance tracking in DPP revisions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.dpps.service import DPPService


class TestTemplateProvenanceStructure:
    """Verify provenance metadata structure."""

    def test_provenance_keys_match_template_keys(self) -> None:
        """Provenance dict should have one entry per template key."""
        expected_fields = {
            "idta_version",
            "semantic_id",
            "resolved_version",
            "source_file_sha",
            "source_file_path",
            "source_kind",
            "selection_strategy",
        }
        entry = {
            "idta_version": "3.0.1",
            "semantic_id": "https://admin-shell.io/idta/SubmodelTemplate/Nameplate/3/0",
            "resolved_version": "V3.0.1",
            "source_file_sha": "abc123",
            "source_file_path": "path/to/file.json",
            "source_kind": "json",
            "selection_strategy": "exact_match_json",
        }
        assert set(entry.keys()) == expected_fields

    def test_provenance_allows_null_values(self) -> None:
        """Provenance should allow None for optional fields."""
        entry = {
            "idta_version": "3.0.1",
            "semantic_id": "https://example.com/sm",
            "resolved_version": None,
            "source_file_sha": None,
            "source_file_path": None,
            "source_kind": None,
            "selection_strategy": None,
        }
        assert len(entry) == 7
        assert entry["resolved_version"] is None


class TestBuildTemplateProvenance:
    """Tests for _build_template_provenance with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_builds_provenance_for_known_template(self) -> None:
        """Provenance should contain all expected fields for a known template."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_template = MagicMock()
        mock_template.resolved_version = "V3.0.1"
        mock_template.source_file_sha = "abc123"
        mock_template.source_file_path = "path/to/file.json"
        mock_template.source_kind = "json"
        mock_template.selection_strategy = "exact_match_json"
        mock_result.scalar_one_or_none.return_value = mock_template
        mock_session.execute.return_value = mock_result

        service = DPPService.__new__(DPPService)
        service._session = mock_session

        with patch("app.modules.dpps.service.get_template_descriptor") as mock_desc:
            mock_desc.return_value = MagicMock(
                baseline_major=3,
                baseline_minor=0,
                semantic_id="https://admin-shell.io/zvei/nameplate/2/0/Nameplate",
            )
            result = await service._build_template_provenance(["nameplate"])

        assert "nameplate" in result
        entry = result["nameplate"]
        assert entry["idta_version"] == "3.0"
        assert entry["semantic_id"] == "https://admin-shell.io/zvei/nameplate/2/0/Nameplate"
        assert entry["source_file_sha"] == "abc123"
        assert entry["resolved_version"] == "V3.0.1"
        assert entry["source_file_path"] == "path/to/file.json"
        assert entry["source_kind"] == "json"
        assert entry["selection_strategy"] == "exact_match_json"

    @pytest.mark.asyncio
    async def test_unknown_template_key_skipped(self) -> None:
        """When descriptor is not found, the key should be skipped entirely."""
        mock_session = AsyncMock()

        service = DPPService.__new__(DPPService)
        service._session = mock_session

        with patch("app.modules.dpps.service.get_template_descriptor") as mock_desc:
            mock_desc.return_value = None
            result = await service._build_template_provenance(["unknown_key"])

        assert "unknown_key" not in result
        assert result == {}

    @pytest.mark.asyncio
    async def test_template_in_catalog_but_not_in_db(self) -> None:
        """When template is in catalog but not DB, descriptor fields set, DB fields None."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Not in DB
        mock_session.execute.return_value = mock_result

        service = DPPService.__new__(DPPService)
        service._session = mock_session

        with patch("app.modules.dpps.service.get_template_descriptor") as mock_desc:
            mock_desc.return_value = MagicMock(
                baseline_major=3,
                baseline_minor=0,
                semantic_id="https://example.com/sm",
            )
            result = await service._build_template_provenance(["nameplate"])

        entry = result["nameplate"]
        assert entry["idta_version"] == "3.0"
        assert entry["semantic_id"] == "https://example.com/sm"
        assert entry["source_file_sha"] is None
        assert entry["source_file_path"] is None
        assert entry["source_kind"] is None
        assert entry["selection_strategy"] is None
        assert entry["resolved_version"] is None

    @pytest.mark.asyncio
    async def test_multiple_template_keys(self) -> None:
        """Provenance should have entries for each known template key."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = DPPService.__new__(DPPService)
        service._session = mock_session

        descriptors = {
            "nameplate": MagicMock(
                baseline_major=3, baseline_minor=0, semantic_id="https://example.com/np"
            ),
            "carbon-footprint": MagicMock(
                baseline_major=1, baseline_minor=0, semantic_id="https://example.com/cf"
            ),
        }

        with patch("app.modules.dpps.service.get_template_descriptor") as mock_desc:
            mock_desc.side_effect = lambda k: descriptors.get(k)
            result = await service._build_template_provenance(
                ["nameplate", "carbon-footprint", "nonexistent"]
            )

        assert "nameplate" in result
        assert "carbon-footprint" in result
        assert "nonexistent" not in result
        assert result["nameplate"]["idta_version"] == "3.0"
        assert result["carbon-footprint"]["idta_version"] == "1.0"
