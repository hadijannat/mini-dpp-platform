# ABAC policies for DPP platform access control

package dpp.authz

import future.keywords.if
import future.keywords.in
import future.keywords.contains

# Default deny
default decision := {
    "effect": "deny",
    "reason": "No matching policy found"
}

# Admin override: allow all actions
decision := {
    "effect": "allow",
    "policy_id": "admin-override"
} if {
    input.subject.is_admin
}

# Tenant admin override within tenant boundary
decision := {
    "effect": "allow",
    "policy_id": "tenant-admin-override"
} if {
    not input.subject.is_admin
    input.subject.is_tenant_admin
    tenant_match
}

# Tenant isolation helper: allow when resource is unscoped or tenant matches
tenant_match if {
    not input.resource.tenant_id
}

tenant_match if {
    input.resource.tenant_id == input.subject.tenant_id
}

# =============================================================================
# Route-Level Policies
# =============================================================================

# Publishers can access all publisher routes
decision := {
    "effect": "allow",
    "policy_id": "route-publisher-access"
} if {
    not input.subject.is_admin
    input.action == "access_route"
    input.resource.route_type == "publisher"
    input.subject.is_publisher
    tenant_match
}

# Viewers can access viewer routes
decision := {
    "effect": "allow",
    "policy_id": "route-viewer-access"
} if {
    not input.subject.is_admin
    input.action == "access_route"
    input.resource.route_type == "viewer"
    tenant_match
}

# Deny viewer access to publisher routes
decision := {
    "effect": "deny",
    "reason": "Publisher role required",
    "policy_id": "route-publisher-deny"
} if {
    not input.subject.is_admin
    input.action == "access_route"
    input.resource.route_type == "publisher"
    not input.subject.is_publisher
    tenant_match
}

# =============================================================================
# DPP Lifecycle Policies
# =============================================================================

# Publishers can create DPPs
decision := {
    "effect": "allow",
    "policy_id": "dpp-create"
} if {
    not input.subject.is_admin
    input.action == "create"
    input.resource.type == "dpp"
    input.subject.is_publisher
    tenant_match
}

# Owners can edit their own DPPs
decision := {
    "effect": "allow",
    "policy_id": "dpp-edit-owner"
} if {
    not input.subject.is_admin
    input.action in ["update", "publish", "archive"]
    input.resource.type == "dpp"
    input.resource.owner_subject == input.subject.sub
    input.subject.is_publisher
    tenant_match
}

# Viewers can only read published DPPs
decision := {
    "effect": "allow",
    "policy_id": "dpp-read-published"
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "dpp"
    input.resource.status == "published"
    tenant_match
}

# Publishers can read their own drafts
decision := {
    "effect": "allow",
    "policy_id": "dpp-read-own-draft"
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "dpp"
    input.resource.status == "draft"
    input.resource.owner_subject == input.subject.sub
    input.subject.is_publisher
    tenant_match
}

# =============================================================================
# Template Policies
# =============================================================================

# All authenticated users can read templates
decision := {
    "effect": "allow",
    "policy_id": "template-read"
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "template"
    tenant_match
}

# Publishers can refresh templates
decision := {
    "effect": "allow",
    "policy_id": "template-refresh"
} if {
    not input.subject.is_admin
    input.action in ["refresh", "update"]
    input.resource.type == "template"
    input.subject.is_publisher
    tenant_match
}

# Deny template refresh for non-publishers
decision := {
    "effect": "deny",
    "reason": "Publisher role required",
    "policy_id": "template-refresh-deny"
} if {
    not input.subject.is_admin
    input.action in ["refresh", "update"]
    input.resource.type == "template"
    not input.subject.is_publisher
    tenant_match
}

# =============================================================================
# DPP Master Policies
# =============================================================================

# Tenant members can read master templates
decision := {
    "effect": "allow",
    "policy_id": "master-read"
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "dpp_master"
    tenant_match
}

# Publishers can create/update/release master templates
decision := {
    "effect": "allow",
    "policy_id": "master-write"
} if {
    not input.subject.is_admin
    input.action in ["create", "update", "release", "archive"]
    input.resource.type == "dpp_master"
    input.subject.is_publisher
    tenant_match
}

# =============================================================================
# Submodel Element Policies
# =============================================================================

# Public elements are always visible
decision := {
    "effect": "allow",
    "policy_id": "element-public"
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "public"
    tenant_match
}

# Internal elements are masked for viewers
decision := {
    "effect": "mask",
    "masked_value": "[INTERNAL]",
    "policy_id": "element-internal-mask"
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "internal"
    not input.subject.is_publisher
    tenant_match
}

# Internal elements visible to publishers
decision := {
    "effect": "allow",
    "policy_id": "element-internal-publisher"
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "internal"
    input.subject.is_publisher
    tenant_match
}

# Confidential elements are hidden from viewers
decision := {
    "effect": "hide",
    "policy_id": "element-confidential-hide"
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "confidential"
    not input.subject.is_publisher
    tenant_match
}

# Confidential elements visible to publishers with clearance
decision := {
    "effect": "allow",
    "policy_id": "element-confidential-cleared"
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "confidential"
    input.subject.is_publisher
    input.subject.clearance in ["confidential", "secret", "top-secret"]
    tenant_match
}

# Encrypted elements require explicit decrypt authorization
decision := {
    "effect": "decrypt",
    "policy_id": "element-encrypted-authorized"
} if {
    not input.subject.is_admin
    input.action == "decrypt"
    input.resource.type == "element"
    input.resource.confidentiality == "encrypted"
    input.subject.is_publisher
    input.subject.clearance in ["secret", "top-secret"]
    tenant_match
}

# =============================================================================
# Connector Policies
# =============================================================================

# Publishers can read connectors
decision := {
    "effect": "allow",
    "policy_id": "connector-read"
} if {
    not input.subject.is_admin
    input.action in ["read", "list"]
    input.resource.type == "connector"
    input.subject.is_publisher
    tenant_match
}

# Publishers can manage connectors
decision := {
    "effect": "allow",
    "policy_id": "connector-manage"
} if {
    not input.subject.is_admin
    input.action in ["create", "update", "delete", "test"]
    input.resource.type == "connector"
    input.subject.is_publisher
    tenant_match
}

# Only owners can publish to connectors
decision := {
    "effect": "allow",
    "policy_id": "connector-publish"
} if {
    not input.subject.is_admin
    input.action == "publish_to_connector"
    input.resource.type == "dpp"
    input.resource.owner_subject == input.subject.sub
    input.subject.is_publisher
    tenant_match
}

# =============================================================================
# Export Policies
# =============================================================================

# Publishers can export any format for their own DPPs
decision := {
    "effect": "allow",
    "policy_id": "export-owner"
} if {
    not input.subject.is_admin
    input.action == "export"
    input.resource.type == "dpp"
    input.resource.owner_subject == input.subject.sub
    input.subject.is_publisher
    tenant_match
}

# Viewers can export published DPPs in limited formats
decision := {
    "effect": "allow",
    "policy_id": "export-viewer-published"
} if {
    not input.subject.is_admin
    input.action == "export"
    input.resource.type == "dpp"
    input.resource.status == "published"
    input.resource.format in ["json", "pdf"]
    not input.subject.is_publisher
    tenant_match
}

# AASX export only for publishers
decision := {
    "effect": "deny",
    "reason": "AASX export requires publisher role",
    "policy_id": "export-aasx-deny"
} if {
    not input.subject.is_admin
    input.action == "export"
    input.resource.format == "aasx"
    not input.subject.is_publisher
    tenant_match
}

# =============================================================================
# BPN-Based Policies (Catena-X)
# =============================================================================

# Same BPN can access shared resources
decision := {
    "effect": "allow",
    "policy_id": "bpn-shared-access"
} if {
    not input.subject.is_admin
    input.action == "read"
    input.resource.type in ["dpp", "element"]
    input.resource.shared_bpns[_] == input.subject.bpn
    input.subject.bpn != null
    tenant_match
}
