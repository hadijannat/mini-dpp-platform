"""Unit tests for controlled ExternalPcfApi resolution in LCAService."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.lca.schemas import ExternalPCFApiRef, MaterialInventory, MaterialItem
from app.modules.lca.service import LCAService


def _service_for_unit() -> LCAService:
    service = LCAService.__new__(LCAService)
    service._session = AsyncMock()
    service._engine = None
    return service


def test_parse_external_pcf_payload_single_item() -> None:
    service = _service_for_unit()
    parsed = service._parse_external_pcf_payload(  # type: ignore[attr-defined]
        {"material_name": "Steel", "pcf_kg_co2e": 7.2}
    )
    assert parsed == [("Steel", 7.2)]


def test_parse_external_pcf_payload_list_items() -> None:
    service = _service_for_unit()
    parsed = service._parse_external_pcf_payload(  # type: ignore[attr-defined]
        {
            "items": [
                {"material_name": "Steel", "pcf_kg_co2e": 7.2},
                {"material_name": "Aluminum", "pcf": 3.1},
            ]
        }
    )
    assert ("Steel", 7.2) in parsed
    assert ("Aluminum", 3.1) in parsed


@pytest.mark.asyncio
async def test_external_pcf_override_blocked_when_host_not_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service_for_unit()
    settings = SimpleNamespace(
        lca_external_pcf_enabled=True,
        lca_external_pcf_allowlist=["allowed.example.com"],
        lca_external_pcf_timeout_seconds=2,
    )
    monkeypatch.setattr("app.modules.lca.service.get_settings", lambda: settings)

    inventory = MaterialInventory(
        items=[MaterialItem(material_name="Steel", category="metal", mass_kg=1.0)],
        external_pcf_apis=[
            ExternalPCFApiRef(
                endpoint="https://blocked.example.com/pcf",
                query="material=Steel",
                source_submodel="CarbonFootprint",
            )
        ],
    )

    updated, log = await service._apply_external_pcf_overrides(inventory)  # type: ignore[attr-defined]
    assert updated.items[0].pre_declared_pcf is None
    assert log and log[0]["status"] == "blocked"
    assert log[0]["reason"] == "host_not_allowlisted"

