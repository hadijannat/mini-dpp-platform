"""Unit tests for EDC ODRL policy builder."""

from __future__ import annotations

from app.modules.connectors.edc.policy_builder import (
    build_access_policy,
    build_usage_policy,
)


class TestBuildAccessPolicy:
    def test_no_bpn_constraints(self) -> None:
        policy = build_access_policy("policy-1", {})

        assert policy.policy_id == "policy-1"
        assert len(policy.policy.permissions) == 1
        assert policy.policy.permissions[0].action == "use"
        assert policy.policy.permissions[0].constraints == []

    def test_single_bpn_constraint(self) -> None:
        policy = build_access_policy(
            "policy-2",
            {"allowed_bpns": ["BPNL000000000001"]},
        )

        constraints = policy.policy.permissions[0].constraints
        assert len(constraints) == 1
        assert constraints[0].left_operand == "BusinessPartnerNumber"
        assert constraints[0].operator == "eq"
        assert constraints[0].right_operand == "BPNL000000000001"

    def test_multiple_bpn_constraints(self) -> None:
        policy = build_access_policy(
            "policy-3",
            {"allowed_bpns": ["BPNL000000000001", "BPNL000000000002"]},
        )

        constraints = policy.policy.permissions[0].constraints
        assert len(constraints) == 1
        assert constraints[0].operator == "in"
        assert "BPNL000000000001" in constraints[0].right_operand
        assert "BPNL000000000002" in constraints[0].right_operand

    def test_payload_serialization(self) -> None:
        policy = build_access_policy("policy-4", {})
        payload = policy.to_edc_payload()

        assert payload["@id"] == "policy-4"
        assert "odrl" in payload["@context"]
        assert payload["policy"]["@type"] == "odrl:Set"


class TestBuildUsagePolicy:
    def test_membership_constraint_always_present(self) -> None:
        policy = build_usage_policy("usage-1", {})

        constraints = policy.policy.permissions[0].constraints
        assert len(constraints) == 1
        assert constraints[0].left_operand == "Membership"
        assert constraints[0].operator == "eq"
        assert constraints[0].right_operand == "active"

    def test_bpn_plus_membership(self) -> None:
        policy = build_usage_policy(
            "usage-2",
            {"allowed_bpns": ["BPNL000000000001"]},
        )

        constraints = policy.policy.permissions[0].constraints
        assert len(constraints) == 2

        operands = {c.left_operand for c in constraints}
        assert "BusinessPartnerNumber" in operands
        assert "Membership" in operands

    def test_payload_serialization(self) -> None:
        policy = build_usage_policy("usage-3", {"allowed_bpns": ["BPN1"]})
        payload = policy.to_edc_payload()

        perm = payload["policy"]["permission"][0]
        constraint_list = perm["constraint"]["and"]
        assert len(constraint_list) == 2
