# DPP, template, export, and ESPR tiered access policies.

package dpp.authz

import future.keywords.if
import future.keywords.in
import future.keywords.contains

policy_candidate contains {
    "priority": 30,
    "decision": {
        "effect": "allow",
        "policy_id": "route-publisher-access",
    },
} if {
    not input.subject.is_admin
    input.action == "access_route"
    input.resource.route_type == "publisher"
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 40,
    "decision": {
        "effect": "allow",
        "policy_id": "route-viewer-access",
    },
} if {
    not input.subject.is_admin
    input.action == "access_route"
    input.resource.route_type == "viewer"
    tenant_match
}

policy_candidate contains {
    "priority": 50,
    "decision": {
        "effect": "deny",
        "reason": "Publisher role required",
        "policy_id": "route-publisher-deny",
    },
} if {
    not input.subject.is_admin
    input.action == "access_route"
    input.resource.route_type == "publisher"
    not input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 60,
    "decision": {
        "effect": "allow",
        "policy_id": "dpp-create",
    },
} if {
    not input.subject.is_admin
    input.action == "create"
    input.resource.type == "dpp"
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 70,
    "decision": {
        "effect": "allow",
        "policy_id": "dpp-edit-owner",
    },
} if {
    not input.subject.is_admin
    input.action in ["update", "publish", "archive"]
    input.resource.type == "dpp"
    input.resource.owner_subject == input.subject.sub
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 80,
    "decision": {
        "effect": "allow",
        "policy_id": "dpp-read-owner-team",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "dpp"
    is_owner_team_accessible
    tenant_match
}

policy_candidate contains {
    "priority": 90,
    "decision": {
        "effect": "allow",
        "policy_id": "dpp-list-owner-team",
    },
} if {
    not input.subject.is_admin
    input.action == "list"
    input.resource.type == "dpp"
    is_owner_team_accessible
    tenant_match
}

policy_candidate contains {
    "priority": 95,
    "decision": {
        "effect": "allow",
        "policy_id": "data-carrier-read-owner-team",
    },
} if {
    not input.subject.is_admin
    input.action in ["read", "render", "pre_sale_pack", "registry_export"]
    input.resource.type == "data_carrier"
    is_owner_team_accessible
    tenant_match
}

policy_candidate contains {
    "priority": 96,
    "decision": {
        "effect": "allow",
        "policy_id": "data-carrier-write-owner",
    },
} if {
    not input.subject.is_admin
    input.action in ["create", "update", "deprecate", "withdraw", "reissue"]
    input.resource.type == "data_carrier"
    input.resource.owner_subject == input.subject.sub
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 100,
    "decision": {
        "effect": "allow",
        "policy_id": "template-read",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "template"
    tenant_match
}

policy_candidate contains {
    "priority": 110,
    "decision": {
        "effect": "allow",
        "policy_id": "template-refresh",
    },
} if {
    not input.subject.is_admin
    input.action in ["refresh", "update"]
    input.resource.type == "template"
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 120,
    "decision": {
        "effect": "deny",
        "reason": "Publisher role required",
        "policy_id": "template-refresh-deny",
    },
} if {
    not input.subject.is_admin
    input.action in ["refresh", "update"]
    input.resource.type == "template"
    not input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 130,
    "decision": {
        "effect": "allow",
        "policy_id": "master-read",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "dpp_master"
    tenant_match
}

policy_candidate contains {
    "priority": 140,
    "decision": {
        "effect": "allow",
        "policy_id": "master-write",
    },
} if {
    not input.subject.is_admin
    input.action in ["create", "update", "release", "archive"]
    input.resource.type == "dpp_master"
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 150,
    "decision": {
        "effect": "allow",
        "policy_id": "element-public",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "public"
    tenant_match
}

policy_candidate contains {
    "priority": 160,
    "decision": {
        "effect": "mask",
        "masked_value": "[INTERNAL]",
        "policy_id": "element-internal-mask",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "internal"
    not input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 170,
    "decision": {
        "effect": "allow",
        "policy_id": "element-internal-publisher",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "internal"
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 180,
    "decision": {
        "effect": "hide",
        "policy_id": "element-confidential-hide",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "confidential"
    not input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 190,
    "decision": {
        "effect": "allow",
        "policy_id": "element-confidential-cleared",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "confidential"
    input.subject.is_publisher
    input.subject.clearance in ["confidential", "secret", "top-secret"]
    tenant_match
}

policy_candidate contains {
    "priority": 200,
    "decision": {
        "effect": "decrypt",
        "policy_id": "element-encrypted-authorized",
    },
} if {
    not input.subject.is_admin
    input.action == "decrypt"
    input.resource.type == "element"
    input.resource.confidentiality == "encrypted"
    input.subject.is_publisher
    input.subject.clearance in ["secret", "top-secret"]
    tenant_match
}

policy_candidate contains {
    "priority": 250,
    "decision": {
        "effect": "allow",
        "policy_id": "export-owner",
    },
} if {
    not input.subject.is_admin
    input.action == "export"
    input.resource.type == "dpp"
    input.resource.owner_subject == input.subject.sub
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 260,
    "decision": {
        "effect": "allow",
        "policy_id": "export-viewer-published",
    },
} if {
    not input.subject.is_admin
    input.action == "export"
    input.resource.type == "dpp"
    input.resource.status == "published"
    input.resource.format in ["json", "pdf"]
    not input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 270,
    "decision": {
        "effect": "deny",
        "reason": "AASX export requires publisher role",
        "policy_id": "export-aasx-deny",
    },
} if {
    not input.subject.is_admin
    input.action == "export"
    input.resource.format == "aasx"
    not input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 280,
    "decision": {
        "effect": "allow",
        "policy_id": "bpn-shared-access",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type in ["dpp", "element"]
    input.resource.shared_bpns[_] == input.subject.bpn
    input.subject.bpn != null
    tenant_match
}

policy_candidate contains {
    "priority": 290,
    "decision": {
        "effect": "allow",
        "policy_id": "espr-consumer-submodel-allow",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "submodel"
    input.subject.espr_tier == "consumer"
    semantic_id_allowed(consumer_allowed)
    tenant_match
}

policy_candidate contains {
    "priority": 300,
    "decision": {
        "effect": "hide",
        "policy_id": "espr-consumer-submodel-hide",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "submodel"
    input.subject.espr_tier == "consumer"
    not semantic_id_allowed(consumer_allowed)
    tenant_match
}

policy_candidate contains {
    "priority": 310,
    "decision": {
        "effect": "allow",
        "policy_id": "espr-recycler-submodel-allow",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "submodel"
    input.subject.espr_tier == "recycler"
    semantic_id_allowed(recycler_allowed)
    tenant_match
}

policy_candidate contains {
    "priority": 320,
    "decision": {
        "effect": "hide",
        "policy_id": "espr-recycler-submodel-hide",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "submodel"
    input.subject.espr_tier == "recycler"
    not semantic_id_allowed(recycler_allowed)
    tenant_match
}

policy_candidate contains {
    "priority": 330,
    "decision": {
        "effect": "allow",
        "policy_id": "espr-authority-submodel-allow",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "submodel"
    input.subject.espr_tier == "market_surveillance_authority"
    tenant_match
}

policy_candidate contains {
    "priority": 340,
    "decision": {
        "effect": "allow",
        "policy_id": "espr-manufacturer-submodel-allow",
    },
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "submodel"
    input.subject.espr_tier == "manufacturer"
    tenant_match
}
