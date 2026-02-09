"""Unit tests for template router contract fields and refresh counters."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.templates.router import (
    _build_template_response,
    list_templates,
    refresh_templates,
)
from app.modules.templates.service import TemplateRefreshResult


def _template_row(template_key: str = "digital-nameplate") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        template_key=template_key,
        idta_version="3.0.1",
        resolved_version="3.0.1",
        semantic_id="https://admin-shell.io/zvei/nameplate/2/0/Nameplate",
        source_url="https://example.com/template.json",
        source_repo_ref="main",
        source_file_path=f"published/{template_key}/3/0/1/template.json",
        source_file_sha="sha-123",
        source_kind="json",
        selection_strategy="deterministic_v2",
        fetched_at=datetime.now(UTC),
    )


class TestBuildTemplateResponse:
    def test_includes_support_metadata_from_catalog_descriptor(self) -> None:
        template = _template_row()
        descriptor = SimpleNamespace(support_status="unavailable", refresh_enabled=False)

        with patch("app.modules.templates.router.get_template_descriptor", return_value=descriptor):
            payload = _build_template_response(template)

        assert payload.support_status == "unavailable"
        assert payload.refresh_enabled is False

    def test_defaults_support_metadata_when_descriptor_missing(self) -> None:
        template = _template_row("custom-template")

        with patch("app.modules.templates.router.get_template_descriptor", return_value=None):
            payload = _build_template_response(template)

        assert payload.support_status == "supported"
        assert payload.refresh_enabled is True


class TestTemplateRouterResponses:
    @pytest.mark.asyncio()
    async def test_list_templates_exposes_support_metadata(self) -> None:
        template = _template_row("battery-passport")
        service = SimpleNamespace(get_all_templates=AsyncMock(return_value=[template]))
        descriptor = SimpleNamespace(support_status="unavailable", refresh_enabled=False)

        with (
            patch("app.modules.templates.router.require_access", new=AsyncMock()),
            patch("app.modules.templates.router.TemplateRegistryService", return_value=service),
            patch("app.modules.templates.router.get_template_descriptor", return_value=descriptor),
        ):
            response = await list_templates(db=AsyncMock(), user=SimpleNamespace())

        assert response.count == 1
        assert response.templates[0].template_key == "battery-passport"
        assert response.templates[0].support_status == "unavailable"
        assert response.templates[0].refresh_enabled is False

    @pytest.mark.asyncio()
    async def test_refresh_templates_returns_counter_summary_and_count_alias(self) -> None:
        template = _template_row("digital-nameplate")
        refresh_results = [
            TemplateRefreshResult(
                template_key="digital-nameplate",
                status="ok",
                support_status="supported",
                idta_version="3.0.1",
                resolved_version="3.0.1",
                source_metadata={
                    "resolved_version": "3.0.1",
                    "source_repo_ref": "main",
                    "source_file_path": "published/nameplate/3/0/1/template.json",
                    "source_file_sha": "sha-ok",
                    "source_kind": "json",
                    "selection_strategy": "deterministic_v2",
                    "source_url": "https://example.com/nameplate.json",
                },
            ),
            TemplateRefreshResult(
                template_key="battery-passport",
                status="skipped",
                support_status="unavailable",
                error="Template is marked as unavailable",
            ),
            TemplateRefreshResult(
                template_key="technical-data",
                status="failed",
                support_status="supported",
                error="fetch failed",
            ),
        ]
        service = SimpleNamespace(
            refresh_all_templates=AsyncMock(return_value=([template], refresh_results))
        )
        descriptor = SimpleNamespace(support_status="supported", refresh_enabled=True)

        with (
            patch("app.modules.templates.router.require_access", new=AsyncMock()),
            patch("app.modules.templates.router.TemplateRegistryService", return_value=service),
            patch("app.modules.templates.router.get_template_descriptor", return_value=descriptor),
        ):
            response = await refresh_templates(db=AsyncMock(), user=SimpleNamespace())

        assert response.attempted_count == 3
        assert response.successful_count == 1
        assert response.failed_count == 1
        assert response.skipped_count == 1
        assert response.count == 1
        assert response.refresh_results is not None
        assert len(response.refresh_results) == 3
