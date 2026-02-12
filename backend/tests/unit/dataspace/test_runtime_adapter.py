"""Unit tests for dataspace runtime adapter resolution."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.dataspace.runtime import (
    CatenaXDTRAdapter,
    EDCAdapter,
    RuntimeConnectorContext,
    get_runtime_adapter,
)


def test_edc_adapter_resolves_secret_ref_for_api_key() -> None:
    adapter = EDCAdapter()
    context = RuntimeConnectorContext(
        connector_id="connector-1",
        runtime="edc",
        participant_id="BPNL000000000001",
        runtime_config={
            "management_url": "http://edc-controlplane:19193/management",
            "management_api_key_secret_ref": "edc-api-key",
            "dsp_endpoint": "http://edc:19194/protocol",
        },
        resolved_secrets={"edc-api-key": "resolved-secret"},
    )

    config = adapter._edc_config(context)  # noqa: SLF001 - intentional unit test of mapping
    assert config.api_key == "resolved-secret"
    assert config.management_url == "http://edc-controlplane:19193/management"
    assert config.dsp_endpoint == "http://edc:19194/protocol"


def test_get_runtime_adapter_returns_edc_adapter() -> None:
    adapter = get_runtime_adapter("edc")
    assert isinstance(adapter, EDCAdapter)


def test_get_runtime_adapter_returns_catenax_adapter() -> None:
    adapter = get_runtime_adapter("catena_x_dtr")
    assert isinstance(adapter, CatenaXDTRAdapter)


def test_get_runtime_adapter_rejects_unknown_runtime() -> None:
    with pytest.raises(ValueError, match="Unsupported runtime adapter"):
        get_runtime_adapter("unsupported-runtime")


@pytest.mark.asyncio
async def test_catenax_adapter_validate_maps_connected_to_ok() -> None:
    adapter = CatenaXDTRAdapter()
    context = RuntimeConnectorContext(
        connector_id="connector-1",
        runtime="catena_x_dtr",
        participant_id="BPNL000000000001",
        runtime_config={
            "dtr_base_url": "https://dtr.example.com",
            "submodel_base_url": "https://public.example.com/submodels",
            "auth_type": "token",
            "token_secret_ref": "dtr-token",
        },
        resolved_secrets={"dtr-token": "secret-token"},
    )

    with patch("app.modules.dataspace.runtime.DTRClient") as dtr_client_cls:
        dtr_client = dtr_client_cls.return_value
        dtr_client.test_connection = AsyncMock(
            return_value={"status": "connected", "dtr_url": "https://dtr.example.com"}
        )
        dtr_client.close = AsyncMock()

        result = await adapter.validate(context)

    assert result["status"] == "ok"
    assert result["runtime"] == "catena_x_dtr"
    assert result["dtr_url"] == "https://dtr.example.com"
    dtr_client.test_connection.assert_awaited_once()
    dtr_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_catenax_adapter_publish_asset_registers_shell_descriptor() -> None:
    adapter = CatenaXDTRAdapter()
    dpp_id = uuid4()
    context = RuntimeConnectorContext(
        connector_id="connector-1",
        runtime="catena_x_dtr",
        participant_id="BPNL000000000001",
        runtime_config={
            "dtr_base_url": "https://dtr.example.com",
            "submodel_base_url": "https://public.example.com",
            "auth_type": "token",
            "token_secret_ref": "dtr-token",
            "edc_dsp_endpoint": "https://edc.example.com/protocol",
        },
        resolved_secrets={"dtr-token": "secret-token"},
    )
    dpp = SimpleNamespace(id=dpp_id, asset_ids={"manufacturerPartId": "AX-42"})
    revision = SimpleNamespace(aas_env_json={"submodels": []})

    with patch("app.modules.dataspace.runtime.DTRClient") as dtr_client_cls:
        dtr_client = dtr_client_cls.return_value
        dtr_client.get_shell = AsyncMock(return_value=None)
        dtr_client.register_shell = AsyncMock(return_value={"id": f"urn:uuid:{dpp_id}"})
        dtr_client.close = AsyncMock()

        result = await adapter.publish_asset(
            context=context,
            dpp=dpp,
            revision=revision,
        )

    assert result.asset_id == f"urn:uuid:{dpp_id}"
    assert result.access_policy_id is None
    assert result.usage_policy_id is None
    assert result.contract_definition_id is None
    dtr_client.get_shell.assert_awaited_once()
    dtr_client.register_shell.assert_awaited_once()
    dtr_client.close.assert_awaited_once()
