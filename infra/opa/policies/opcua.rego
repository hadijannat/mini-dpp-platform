# OPC UA source, nodeset, mapping, job, and deadletter access policies.

package dpp.authz

import future.keywords.if
import future.keywords.in
import future.keywords.contains

# --- OPC UA Source ---

policy_candidate contains {
    "priority": 400,
    "decision": {
        "effect": "allow",
        "policy_id": "opcua-source-read",
    },
} if {
    not input.subject.is_admin
    input.action in ["read", "list"]
    input.resource.type == "opcua_source"
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 410,
    "decision": {
        "effect": "allow",
        "policy_id": "opcua-source-create",
    },
} if {
    not input.subject.is_admin
    input.action == "create"
    input.resource.type == "opcua_source"
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 420,
    "decision": {
        "effect": "allow",
        "policy_id": "opcua-source-manage",
    },
} if {
    not input.subject.is_admin
    input.action in ["update", "delete", "test"]
    input.resource.type == "opcua_source"
    input.subject.is_publisher
    is_owner
    tenant_match
}

policy_candidate contains {
    "priority": 425,
    "decision": {
        "effect": "deny",
        "reason": "Publisher role required for OPC UA source access",
        "policy_id": "opcua-source-deny-viewer",
    },
} if {
    not input.subject.is_admin
    input.resource.type == "opcua_source"
    not input.subject.is_publisher
    tenant_match
}

# --- OPC UA NodeSet ---

policy_candidate contains {
    "priority": 430,
    "decision": {
        "effect": "allow",
        "policy_id": "opcua-nodeset-read",
    },
} if {
    not input.subject.is_admin
    input.action in ["read", "list", "download"]
    input.resource.type == "opcua_nodeset"
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 440,
    "decision": {
        "effect": "allow",
        "policy_id": "opcua-nodeset-upload",
    },
} if {
    not input.subject.is_admin
    input.action in ["create", "upload"]
    input.resource.type == "opcua_nodeset"
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 450,
    "decision": {
        "effect": "allow",
        "policy_id": "opcua-nodeset-delete",
    },
} if {
    not input.subject.is_admin
    input.action == "delete"
    input.resource.type == "opcua_nodeset"
    input.subject.is_publisher
    is_owner
    tenant_match
}

# --- OPC UA Mapping ---

policy_candidate contains {
    "priority": 460,
    "decision": {
        "effect": "allow",
        "policy_id": "opcua-mapping-read",
    },
} if {
    not input.subject.is_admin
    input.action in ["read", "list"]
    input.resource.type == "opcua_mapping"
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 470,
    "decision": {
        "effect": "allow",
        "policy_id": "opcua-mapping-write",
    },
} if {
    not input.subject.is_admin
    input.action in ["create", "update", "delete", "validate", "dry_run"]
    input.resource.type == "opcua_mapping"
    input.subject.is_publisher
    tenant_match
}

# --- OPC UA Job ---

policy_candidate contains {
    "priority": 480,
    "decision": {
        "effect": "allow",
        "policy_id": "opcua-job-read",
    },
} if {
    not input.subject.is_admin
    input.action in ["read", "list"]
    input.resource.type == "opcua_job"
    input.subject.is_publisher
    tenant_match
}

# --- OPC UA Dead Letter ---

policy_candidate contains {
    "priority": 490,
    "decision": {
        "effect": "allow",
        "policy_id": "opcua-deadletter-read",
    },
} if {
    not input.subject.is_admin
    input.action in ["read", "list"]
    input.resource.type == "opcua_deadletter"
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 495,
    "decision": {
        "effect": "allow",
        "policy_id": "opcua-deadletter-manage",
    },
} if {
    not input.subject.is_admin
    input.action in ["delete", "retry"]
    input.resource.type == "opcua_deadletter"
    input.subject.is_publisher
    tenant_match
}

# --- Dataspace Publication ---

policy_candidate contains {
    "priority": 500,
    "decision": {
        "effect": "allow",
        "policy_id": "ds-publication-read",
    },
} if {
    not input.subject.is_admin
    input.action in ["read", "list"]
    input.resource.type == "dataspace_publication"
    input.subject.is_publisher
    tenant_match
}

policy_candidate contains {
    "priority": 510,
    "decision": {
        "effect": "allow",
        "policy_id": "ds-publication-create",
    },
} if {
    not input.subject.is_admin
    input.action == "create"
    input.resource.type == "dataspace_publication"
    input.subject.is_publisher
    tenant_match
}
