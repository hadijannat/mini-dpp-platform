"""Unit tests for EDC Pydantic models and payload serialization."""

from app.modules.connectors.edc.models import (
    ContractDefinition,
    DataAddress,
    EDCAsset,
    ODRLConstraint,
    ODRLPermission,
    ODRLPolicy,
    PolicyDefinition,
)


class TestDataAddress:
    def test_to_edc_payload_defaults(self) -> None:
        addr = DataAddress(base_url="https://example.com/api")
        payload = addr.to_edc_payload()

        assert payload["@type"] == "DataAddress"
        assert payload["type"] == "HttpData"
        assert payload["baseUrl"] == "https://example.com/api"
        assert payload["proxyBody"] == "false"
        assert payload["proxyPath"] == "true"
        assert payload["proxyQueryParams"] == "true"

    def test_to_edc_payload_custom(self) -> None:
        addr = DataAddress(
            type="S3",
            base_url="s3://bucket/prefix",
            proxy_body=True,
            proxy_path=False,
            proxy_query_params=False,
        )
        payload = addr.to_edc_payload()

        assert payload["type"] == "S3"
        assert payload["proxyBody"] == "true"
        assert payload["proxyPath"] == "false"


class TestEDCAsset:
    def test_to_edc_payload(self) -> None:
        asset = EDCAsset(
            asset_id="dpp-abc123",
            properties={"name": "Test DPP", "contenttype": "application/json"},
            data_address=DataAddress(base_url="https://dpp.dev/api/v1/public/dpps/abc123"),
        )
        payload = asset.to_edc_payload()

        assert payload["@id"] == "dpp-abc123"
        assert payload["@context"]["edc"] == "https://w3id.org/edc/v0.0.1/ns/"
        assert payload["properties"]["name"] == "Test DPP"
        assert payload["dataAddress"]["@type"] == "DataAddress"
        assert "abc123" in payload["dataAddress"]["baseUrl"]


class TestODRLPolicy:
    def test_empty_policy(self) -> None:
        policy = ODRLPolicy()
        payload = policy.to_edc_payload()

        assert payload["@type"] == "odrl:Set"
        assert payload["permission"] == []
        assert payload["prohibition"] == []
        assert payload["obligation"] == []

    def test_policy_with_constraints(self) -> None:
        constraint = ODRLConstraint(
            left_operand="BusinessPartnerNumber",
            operator="eq",
            right_operand="BPNL123",
        )
        permission = ODRLPermission(action="use", constraints=[constraint])
        policy = ODRLPolicy(permissions=[permission])
        payload = policy.to_edc_payload()

        perm = payload["permission"][0]
        assert perm["action"] == "use"
        assert perm["constraint"]["and"][0]["leftOperand"] == "BusinessPartnerNumber"
        assert perm["constraint"]["and"][0]["operator"] == "eq"
        assert perm["constraint"]["and"][0]["rightOperand"] == "BPNL123"


class TestPolicyDefinition:
    def test_to_edc_payload(self) -> None:
        policy_def = PolicyDefinition(
            policy_id="policy-1",
            policy=ODRLPolicy(permissions=[ODRLPermission(action="use")]),
        )
        payload = policy_def.to_edc_payload()

        assert payload["@id"] == "policy-1"
        assert "odrl" in payload["@context"]
        assert payload["policy"]["@type"] == "odrl:Set"


class TestContractDefinition:
    def test_to_edc_payload(self) -> None:
        contract = ContractDefinition(
            contract_id="contract-1",
            access_policy_id="access-1",
            contract_policy_id="usage-1",
            asset_selector={
                "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
                "operator": "=",
                "operandRight": "dpp-abc",
            },
        )
        payload = contract.to_edc_payload()

        assert payload["@id"] == "contract-1"
        assert payload["accessPolicyId"] == "access-1"
        assert payload["contractPolicyId"] == "usage-1"
        assert payload["assetsSelector"]["operator"] == "="
