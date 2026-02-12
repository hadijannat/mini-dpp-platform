# Admin and tenant-admin override policies.

package dpp.authz

import future.keywords.if
import future.keywords.contains

policy_candidate contains {
    "priority": 10,
    "decision": {
        "effect": "allow",
        "policy_id": "admin-override",
    },
} if {
    input.subject.is_admin
}

policy_candidate contains {
    "priority": 20,
    "decision": {
        "effect": "allow",
        "policy_id": "tenant-admin-override",
    },
} if {
    not input.subject.is_admin
    input.subject.is_tenant_admin
    tenant_match
}
