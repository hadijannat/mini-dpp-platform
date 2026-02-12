# Dataspace-specific sharing policies.

package dpp.authz

import future.keywords.if
import future.keywords.contains

policy_candidate contains {
    "priority": 240,
    "decision": {
        "effect": "allow",
        "policy_id": "connector-publish",
    },
} if {
    not input.subject.is_admin
    input.action == "publish_to_connector"
    input.resource.type == "dpp"
    input.resource.owner_subject == input.subject.sub
    input.subject.is_publisher
    tenant_match
}
