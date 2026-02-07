"""Unit tests for EDCManagementClient with mocked HTTP responses."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.modules.connectors.edc.client import EDCConfig, EDCManagementClient
from app.modules.connectors.edc.models import (
    ContractDefinition,
    DataAddress,
    EDCAsset,
    ODRLPermission,
    ODRLPolicy,
    PolicyDefinition,
)


@pytest.fixture
def edc_config() -> EDCConfig:
    return EDCConfig(
        management_url="http://edc-test:19193",
        api_key="test-key",
        dsp_endpoint="http://edc-test:19194/protocol",
        participant_id="BPNL000TEST",
    )


@pytest.fixture
def sample_asset() -> EDCAsset:
    return EDCAsset(
        asset_id="dpp-test-123",
        properties={"name": "Test DPP"},
        data_address=DataAddress(base_url="https://dpp.dev/api/v1/public/dpps/test-123"),
    )


@pytest.fixture
def sample_policy() -> PolicyDefinition:
    return PolicyDefinition(
        policy_id="access-dpp-test-123",
        policy=ODRLPolicy(permissions=[ODRLPermission(action="use")]),
    )


@pytest.fixture
def sample_contract() -> ContractDefinition:
    return ContractDefinition(
        contract_id="contract-dpp-test-123",
        access_policy_id="access-dpp-test-123",
        contract_policy_id="usage-dpp-test-123",
        asset_selector={
            "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
            "operator": "=",
            "operandRight": "dpp-test-123",
        },
    )


class TestEDCManagementClientConfig:
    def test_empty_url_raises(self) -> None:
        config = EDCConfig(management_url="")
        client = EDCManagementClient(config)
        with pytest.raises(ValueError, match="management URL is required"):
            client._validate_config()

    def test_trailing_slash_stripped(self) -> None:
        config = EDCConfig(management_url="http://edc:19193/")
        client = EDCManagementClient(config)
        client._validate_config()
        assert config.management_url == "http://edc:19193"


class TestEDCManagementClientAssets:
    @pytest.mark.asyncio
    async def test_create_asset(
        self, edc_config: EDCConfig, sample_asset: EDCAsset
    ) -> None:
        client = EDCManagementClient(edc_config)

        mock_response = httpx.Response(
            200,
            json={"@id": "dpp-test-123", "@type": "Asset"},
            request=httpx.Request("POST", "http://test"),
        )

        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.create_asset(sample_asset)

        assert result["@id"] == "dpp-test-123"
        await client.close()

    @pytest.mark.asyncio
    async def test_get_asset_found(self, edc_config: EDCConfig) -> None:
        client = EDCManagementClient(edc_config)

        mock_response = httpx.Response(
            200,
            json={"@id": "dpp-test-123", "properties": {}},
            request=httpx.Request("GET", "http://test"),
        )

        with patch.object(
            httpx.AsyncClient,
            "get",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.get_asset("dpp-test-123")

        assert result is not None
        assert result["@id"] == "dpp-test-123"
        await client.close()

    @pytest.mark.asyncio
    async def test_get_asset_not_found(self, edc_config: EDCConfig) -> None:
        client = EDCManagementClient(edc_config)

        mock_response = httpx.Response(
            404,
            json={"error": "not found"},
            request=httpx.Request("GET", "http://test"),
        )

        with patch.object(
            httpx.AsyncClient,
            "get",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.get_asset("nonexistent")

        assert result is None
        await client.close()

    @pytest.mark.asyncio
    async def test_delete_asset(self, edc_config: EDCConfig) -> None:
        client = EDCManagementClient(edc_config)

        mock_response = httpx.Response(
            204,
            request=httpx.Request("DELETE", "http://test"),
        )

        with patch.object(
            httpx.AsyncClient,
            "delete",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.delete_asset("dpp-test-123")

        assert result is True
        await client.close()


class TestEDCManagementClientPolicies:
    @pytest.mark.asyncio
    async def test_create_policy(
        self, edc_config: EDCConfig, sample_policy: PolicyDefinition
    ) -> None:
        client = EDCManagementClient(edc_config)

        mock_response = httpx.Response(
            200,
            json={"@id": "access-dpp-test-123"},
            request=httpx.Request("POST", "http://test"),
        )

        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.create_policy(sample_policy)

        assert result["@id"] == "access-dpp-test-123"
        await client.close()


class TestEDCManagementClientContracts:
    @pytest.mark.asyncio
    async def test_create_contract_definition(
        self, edc_config: EDCConfig, sample_contract: ContractDefinition
    ) -> None:
        client = EDCManagementClient(edc_config)

        mock_response = httpx.Response(
            200,
            json={"@id": "contract-dpp-test-123"},
            request=httpx.Request("POST", "http://test"),
        )

        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.create_contract_definition(sample_contract)

        assert result["@id"] == "contract-dpp-test-123"
        await client.close()


class TestEDCManagementClientNegotiation:
    @pytest.mark.asyncio
    async def test_initiate_negotiation(self, edc_config: EDCConfig) -> None:
        client = EDCManagementClient(edc_config)

        mock_response = httpx.Response(
            200,
            json={
                "@id": "neg-001",
                "state": "REQUESTED",
                "contractAgreementId": None,
            },
            request=httpx.Request("POST", "http://test"),
        )

        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.initiate_negotiation(
                connector_address="http://consumer:19194/protocol",
                offer_id="offer-1",
                asset_id="dpp-test-123",
                policy={"@type": "odrl:Set"},
            )

        assert result.negotiation_id == "neg-001"
        assert result.state == "REQUESTED"
        await client.close()

    @pytest.mark.asyncio
    async def test_get_negotiation(self, edc_config: EDCConfig) -> None:
        client = EDCManagementClient(edc_config)

        mock_response = httpx.Response(
            200,
            json={
                "@id": "neg-001",
                "state": "FINALIZED",
                "contractAgreementId": "agreement-001",
            },
            request=httpx.Request("GET", "http://test"),
        )

        with patch.object(
            httpx.AsyncClient,
            "get",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.get_negotiation("neg-001")

        assert result.state == "FINALIZED"
        assert result.contract_agreement_id == "agreement-001"
        await client.close()


class TestEDCManagementClientTransfer:
    @pytest.mark.asyncio
    async def test_initiate_transfer(self, edc_config: EDCConfig) -> None:
        client = EDCManagementClient(edc_config)

        mock_response = httpx.Response(
            200,
            json={"@id": "transfer-001", "state": "INITIAL"},
            request=httpx.Request("POST", "http://test"),
        )

        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.initiate_transfer(
                connector_address="http://consumer:19194/protocol",
                contract_agreement_id="agreement-001",
                asset_id="dpp-test-123",
                data_destination={"type": "HttpProxy"},
            )

        assert result.transfer_id == "transfer-001"
        assert result.state == "INITIAL"
        await client.close()


class TestEDCManagementClientHealth:
    @pytest.mark.asyncio
    async def test_health_ok(self, edc_config: EDCConfig) -> None:
        client = EDCManagementClient(edc_config)

        mock_response = httpx.Response(
            200,
            json={"componentResults": [{"component": "default", "isSystemHealthy": True}]},
            request=httpx.Request("GET", "http://test"),
        )

        with patch.object(
            httpx.AsyncClient,
            "get",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.check_health()

        assert "componentResults" in result
        await client.close()

    @pytest.mark.asyncio
    async def test_health_error(self, edc_config: EDCConfig) -> None:
        client = EDCManagementClient(edc_config)

        mock_response = httpx.Response(
            503,
            json={"error": "unavailable"},
            request=httpx.Request("GET", "http://test"),
        )

        with patch.object(
            httpx.AsyncClient,
            "get",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.check_health()

        assert result["status"] == "error"
        assert result["error_code"] == 503
        await client.close()

    @pytest.mark.asyncio
    async def test_health_connection_error(self, edc_config: EDCConfig) -> None:
        client = EDCManagementClient(edc_config)

        with patch.object(
            httpx.AsyncClient,
            "get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("refused"),
        ):
            result = await client.check_health()

        assert result["status"] == "error"
        assert "refused" in result["error_message"]
        await client.close()

    @pytest.mark.asyncio
    async def test_close_idempotent(self, edc_config: EDCConfig) -> None:
        client = EDCManagementClient(edc_config)
        await client.close()
        await client.close()  # should not raise
