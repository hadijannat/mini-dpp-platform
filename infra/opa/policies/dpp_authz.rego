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

# =============================================================================
# Route-Level Policies
# =============================================================================

# Publishers can access all publisher routes
decision := {
    "effect": "allow",
    "policy_id": "route-publisher-access"
} if {
    input.action == "access_route"
    input.resource.route_type == "publisher"
    input.subject.is_publisher
}

# Viewers can access viewer routes
decision := {
    "effect": "allow",
    "policy_id": "route-viewer-access"
} if {
    input.action == "access_route"
    input.resource.route_type == "viewer"
}

# Deny viewer access to publisher routes
decision := {
    "effect": "deny",
    "reason": "Publisher role required",
    "policy_id": "route-publisher-deny"
} if {
    input.action == "access_route"
    input.resource.route_type == "publisher"
    not input.subject.is_publisher
}

# =============================================================================
# DPP Lifecycle Policies
# =============================================================================

# Publishers can create DPPs
decision := {
    "effect": "allow",
    "policy_id": "dpp-create"
} if {
    input.action == "create"
    input.resource.type == "dpp"
    input.subject.is_publisher
}

# Owners can edit their own DPPs
decision := {
    "effect": "allow",
    "policy_id": "dpp-edit-owner"
} if {
    input.action in ["update", "publish", "archive"]
    input.resource.type == "dpp"
    input.resource.owner_subject == input.subject.sub
    input.subject.is_publisher
}

# Viewers can only read published DPPs
decision := {
    "effect": "allow",
    "policy_id": "dpp-read-published"
} if {
    input.action == "read"
    input.resource.type == "dpp"
    input.resource.status == "published"
}

# Publishers can read their own drafts
decision := {
    "effect": "allow",
    "policy_id": "dpp-read-own-draft"
} if {
    input.action == "read"
    input.resource.type == "dpp"
    input.resource.status == "draft"
    input.resource.owner_subject == input.subject.sub
    input.subject.is_publisher
}

# =============================================================================
# Template Policies
# =============================================================================

# All authenticated users can read templates
decision := {
    "effect": "allow",
    "policy_id": "template-read"
} if {
    input.action == "read"
    input.resource.type == "template"
}

# Publishers can refresh templates
decision := {
    "effect": "allow",
    "policy_id": "template-refresh"
} if {
    input.action in ["refresh", "update"]
    input.resource.type == "template"
    input.subject.is_publisher
}

# Deny template refresh for non-publishers
decision := {
    "effect": "deny",
    "reason": "Publisher role required",
    "policy_id": "template-refresh-deny"
} if {
    input.action in ["refresh", "update"]
    input.resource.type == "template"
    not input.subject.is_publisher
}

# =============================================================================
# Submodel Element Policies
# =============================================================================

# Public elements are always visible
decision := {
    "effect": "allow",
    "policy_id": "element-public"
} if {
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "public"
}

# Internal elements are masked for viewers
decision := {
    "effect": "mask",
    "masked_value": "[INTERNAL]",
    "policy_id": "element-internal-mask"
} if {
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "internal"
    not input.subject.is_publisher
}

# Internal elements visible to publishers
decision := {
    "effect": "allow",
    "policy_id": "element-internal-publisher"
} if {
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "internal"
    input.subject.is_publisher
}

# Confidential elements are hidden from viewers
decision := {
    "effect": "hide",
    "policy_id": "element-confidential-hide"
} if {
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "confidential"
    not input.subject.is_publisher
}

# Confidential elements visible to publishers with clearance
decision := {
    "effect": "allow",
    "policy_id": "element-confidential-cleared"
} if {
    input.action == "read"
    input.resource.type == "element"
    input.resource.confidentiality == "confidential"
    input.subject.is_publisher
    input.subject.clearance in ["confidential", "secret", "top-secret"]
}

# Encrypted elements require explicit decrypt authorization
decision := {
    "effect": "decrypt",
    "policy_id": "element-encrypted-authorized"
} if {
    input.action == "decrypt"
    input.resource.type == "element"
    input.resource.confidentiality == "encrypted"
    input.subject.is_publisher
    input.subject.clearance in ["secret", "top-secret"]
}

# =============================================================================
# Connector Policies
# =============================================================================

# Publishers can read connectors
decision := {
    "effect": "allow",
    "policy_id": "connector-read"
} if {
    input.action in ["read", "list"]
    input.resource.type == "connector"
    input.subject.is_publisher
}

# Publishers can manage connectors
decision := {
    "effect": "allow",
    "policy_id": "connector-manage"
} if {
    input.action in ["create", "update", "delete", "test"]
    input.resource.type == "connector"
    input.subject.is_publisher
}

# Only owners can publish to connectors
decision := {
    "effect": "allow",
    "policy_id": "connector-publish"
} if {
    input.action == "publish_to_connector"
    input.resource.type == "dpp"
    input.resource.owner_subject == input.subject.sub
    input.subject.is_publisher
}

# =============================================================================
# Export Policies
# =============================================================================

# Publishers can export any format for their own DPPs
decision := {
    "effect": "allow",
    "policy_id": "export-owner"
} if {
    input.action == "export"
    input.resource.type == "dpp"
    input.resource.owner_subject == input.subject.sub
    input.subject.is_publisher
}

# Viewers can export published DPPs in limited formats
decision := {
    "effect": "allow",
    "policy_id": "export-viewer-published"
} if {
    input.action == "export"
    input.resource.type == "dpp"
    input.resource.status == "published"
    input.resource.format in ["json", "pdf"]
    not input.subject.is_publisher
}

# AASX export only for publishers
decision := {
    "effect": "deny",
    "reason": "AASX export requires publisher role",
    "policy_id": "export-aasx-deny"
} if {
    input.action == "export"
    input.resource.format == "aasx"
    not input.subject.is_publisher
}

# =============================================================================
# BPN-Based Policies (Catena-X)
# =============================================================================

# Same BPN can access shared resources
decision := {
    "effect": "allow",
    "policy_id": "bpn-shared-access"
} if {
    input.action == "read"
    input.resource.type in ["dpp", "element"]
    input.resource.shared_bpns[_] == input.subject.bpn
    input.subject.bpn != null
}
