# Connector lifecycle and access policies.

package dpp.authz

import future.keywords.if
import future.keywords.in
import future.keywords.contains

policy_candidate contains {
    "priority": 210,
    "decision": {
        "effect": "allow",
        "policy_id": "connector-read",
    },
} if {
    not input.subject.is_admin
    input.action in ["read", "list"]
    input.resource.type == "connector"
    input.subject.is_publisher
    is_owner_team_accessible
    tenant_match
}

policy_candidate contains {
    "priority": 220,
    "decision": {
        "effect": "allow",
        "policy_id": "connector-create",
    },
} if {
    not input.subject.is_admin
    input.action == "create"
    input.resource.type == "connector"
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 230,
    "decision": {
        "effect": "allow",
        "policy_id": "connector-manage-owner-team",
    },
} if {
    not input.subject.is_admin
    input.action in ["update", "delete", "test"]
    input.resource.type == "connector"
    input.subject.is_publisher
    is_owner
    tenant_match
}
