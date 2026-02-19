package dpp.authz_test

import data.dpp.authz.decision

test_default_deny_for_unknown_resource {
    result := decision with input as {
        "subject": {
            "sub": "viewer-1",
            "tenant_id": "tenant-a",
            "is_admin": false,
            "is_tenant_admin": false,
            "is_publisher": false,
        },
        "action": "read",
        "resource": {
            "type": "unknown",
            "tenant_id": "tenant-a",
        },
    }
    result.effect == "deny"
    result.reason == "No matching policy found"
}

test_admin_override_ignores_tenant_scope {
    result := decision with input as {
        "subject": {
            "sub": "admin-1",
            "tenant_id": "tenant-a",
            "is_admin": true,
            "is_tenant_admin": false,
            "is_publisher": false,
        },
        "action": "read",
        "resource": {
            "type": "connector",
            "tenant_id": "tenant-b",
        },
    }
    result.effect == "allow"
    result.policy_id == "admin-override"
}

test_template_refresh_denied_for_non_publisher {
    result := decision with input as {
        "subject": {
            "sub": "viewer-1",
            "tenant_id": "tenant-a",
            "is_admin": false,
            "is_tenant_admin": false,
            "is_publisher": false,
        },
        "action": "refresh",
        "resource": {
            "type": "template",
            "tenant_id": "tenant-a",
        },
    }
    result.effect == "deny"
    result.policy_id == "template-refresh-deny"
}

test_connector_read_allows_owner_team_scope_for_publisher {
    result := decision with input as {
        "subject": {
            "sub": "publisher-1",
            "tenant_id": "tenant-a",
            "is_admin": false,
            "is_tenant_admin": false,
            "is_publisher": true,
        },
        "action": "read",
        "resource": {
            "type": "connector",
            "tenant_id": "tenant-a",
            "owner_subject": "publisher-1",
            "shared_with_current_user": false,
            "visibility_scope": "owner_team",
        },
    }
    result.effect == "allow"
    result.policy_id == "connector-read"
}

test_publish_to_connector_requires_owner {
    denied := decision with input as {
        "subject": {
            "sub": "publisher-2",
            "tenant_id": "tenant-a",
            "is_admin": false,
            "is_tenant_admin": false,
            "is_publisher": true,
        },
        "action": "publish_to_connector",
        "resource": {
            "type": "dpp",
            "tenant_id": "tenant-a",
            "owner_subject": "publisher-1",
        },
    }
    denied.effect == "deny"

    allowed := decision with input as {
        "subject": {
            "sub": "publisher-1",
            "tenant_id": "tenant-a",
            "is_admin": false,
            "is_tenant_admin": false,
            "is_publisher": true,
        },
        "action": "publish_to_connector",
        "resource": {
            "type": "dpp",
            "tenant_id": "tenant-a",
            "owner_subject": "publisher-1",
        },
    }
    allowed.effect == "allow"
    allowed.policy_id == "connector-publish"
}

test_espr_consumer_submodel_hide_when_not_allowed {
    result := decision with input as {
        "subject": {
            "sub": "consumer-1",
            "tenant_id": "tenant-a",
            "is_admin": false,
            "is_tenant_admin": false,
            "is_publisher": false,
            "espr_tier": "consumer",
        },
        "action": "read",
        "resource": {
            "type": "submodel",
            "tenant_id": "tenant-a",
            "semantic_id": "https://example.com/unknown/submodel",
        },
    }
    result.effect == "hide"
    result.policy_id == "espr-consumer-submodel-hide"
}

# --- OPC UA Source ---

test_opcua_source_read_allowed_for_publisher {
    result := decision with input as {
        "subject": {
            "sub": "publisher-1",
            "tenant_id": "tenant-a",
            "is_admin": false,
            "is_tenant_admin": false,
            "is_publisher": true,
        },
        "action": "read",
        "resource": {
            "type": "opcua_source",
            "tenant_id": "tenant-a",
            "owner_subject": "publisher-1",
        },
    }
    result.effect == "allow"
    result.policy_id == "opcua-source-read"
}

test_opcua_source_denied_for_viewer {
    result := decision with input as {
        "subject": {
            "sub": "viewer-1",
            "tenant_id": "tenant-a",
            "is_admin": false,
            "is_tenant_admin": false,
            "is_publisher": false,
        },
        "action": "read",
        "resource": {
            "type": "opcua_source",
            "tenant_id": "tenant-a",
        },
    }
    result.effect == "deny"
    result.policy_id == "opcua-source-deny-viewer"
}

test_opcua_source_manage_requires_owner {
    denied := decision with input as {
        "subject": {
            "sub": "publisher-2",
            "tenant_id": "tenant-a",
            "is_admin": false,
            "is_tenant_admin": false,
            "is_publisher": true,
        },
        "action": "delete",
        "resource": {
            "type": "opcua_source",
            "tenant_id": "tenant-a",
            "owner_subject": "publisher-1",
        },
    }
    denied.effect == "deny"

    allowed := decision with input as {
        "subject": {
            "sub": "publisher-1",
            "tenant_id": "tenant-a",
            "is_admin": false,
            "is_tenant_admin": false,
            "is_publisher": true,
        },
        "action": "delete",
        "resource": {
            "type": "opcua_source",
            "tenant_id": "tenant-a",
            "owner_subject": "publisher-1",
        },
    }
    allowed.effect == "allow"
    allowed.policy_id == "opcua-source-manage"
}

test_opcua_source_cross_tenant_denied {
    result := decision with input as {
        "subject": {
            "sub": "publisher-1",
            "tenant_id": "tenant-b",
            "is_admin": false,
            "is_tenant_admin": false,
            "is_publisher": true,
        },
        "action": "read",
        "resource": {
            "type": "opcua_source",
            "tenant_id": "tenant-a",
            "owner_subject": "publisher-1",
        },
    }
    result.effect == "deny"
}

# --- OPC UA Mapping ---

test_opcua_mapping_write_allowed_for_publisher {
    result := decision with input as {
        "subject": {
            "sub": "publisher-1",
            "tenant_id": "tenant-a",
            "is_admin": false,
            "is_tenant_admin": false,
            "is_publisher": true,
        },
        "action": "validate",
        "resource": {
            "type": "opcua_mapping",
            "tenant_id": "tenant-a",
        },
    }
    result.effect == "allow"
    result.policy_id == "opcua-mapping-write"
}

# --- OPC UA Dead Letter ---

test_opcua_deadletter_read_allowed_for_publisher {
    result := decision with input as {
        "subject": {
            "sub": "publisher-1",
            "tenant_id": "tenant-a",
            "is_admin": false,
            "is_tenant_admin": false,
            "is_publisher": true,
        },
        "action": "list",
        "resource": {
            "type": "opcua_deadletter",
            "tenant_id": "tenant-a",
        },
    }
    result.effect == "allow"
    result.policy_id == "opcua-deadletter-read"
}

# --- Dataspace Publication ---

test_ds_publication_create_allowed_for_publisher {
    result := decision with input as {
        "subject": {
            "sub": "publisher-1",
            "tenant_id": "tenant-a",
            "is_admin": false,
            "is_tenant_admin": false,
            "is_publisher": true,
        },
        "action": "create",
        "resource": {
            "type": "dataspace_publication",
            "tenant_id": "tenant-a",
        },
    }
    result.effect == "allow"
    result.policy_id == "ds-publication-create"
}
