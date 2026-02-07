"""
ODRL policy generation for EDC asset access and usage control.

Default policies enforce BPN-restricted access following the
Catena-X membership verification pattern.
"""

from __future__ import annotations

from typing import Any

from app.modules.connectors.edc.models import (
    ODRLConstraint,
    ODRLPermission,
    ODRLPolicy,
    PolicyDefinition,
)


def build_access_policy(
    policy_id: str,
    connector_config: dict[str, Any],
) -> PolicyDefinition:
    """
    Build an ODRL access policy for a DPP asset.

    If the connector config contains ``allowed_bpns``, the policy restricts
    access to those Business Partner Numbers.  Otherwise a permissive
    "use" permission is generated.

    Args:
        policy_id: Unique identifier for this policy definition.
        connector_config: Connector-level configuration dict (JSONB from DB).

    Returns:
        A ``PolicyDefinition`` ready for EDC registration.
    """
    constraints = _bpn_constraints(connector_config)

    permission = ODRLPermission(
        action="use",
        constraints=constraints,
    )

    policy = ODRLPolicy(
        permissions=[permission],
    )

    return PolicyDefinition(policy_id=policy_id, policy=policy)


def build_usage_policy(
    policy_id: str,
    connector_config: dict[str, Any],
) -> PolicyDefinition:
    """
    Build an ODRL usage (contract) policy for a DPP asset.

    Adds a Catena-X membership verification constraint on top of
    any BPN restrictions from the connector config.

    Args:
        policy_id: Unique identifier for this policy definition.
        connector_config: Connector-level configuration dict (JSONB from DB).

    Returns:
        A ``PolicyDefinition`` ready for EDC registration.
    """
    constraints = _bpn_constraints(connector_config)

    # Require Catena-X membership verification
    constraints.append(
        ODRLConstraint(
            left_operand="Membership",
            operator="eq",
            right_operand="active",
        )
    )

    permission = ODRLPermission(
        action="use",
        constraints=constraints,
    )

    policy = ODRLPolicy(
        permissions=[permission],
    )

    return PolicyDefinition(policy_id=policy_id, policy=policy)


def _bpn_constraints(
    connector_config: dict[str, Any],
) -> list[ODRLConstraint]:
    """Extract BPN constraints from connector configuration."""
    allowed_bpns: list[str] = connector_config.get("allowed_bpns", [])
    if not allowed_bpns:
        return []

    return [
        ODRLConstraint(
            left_operand="BusinessPartnerNumber",
            operator="in" if len(allowed_bpns) > 1 else "eq",
            right_operand=",".join(allowed_bpns) if len(allowed_bpns) > 1 else allowed_bpns[0],
        )
    ]
