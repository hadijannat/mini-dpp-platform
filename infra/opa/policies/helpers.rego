# Shared helpers for modular ABAC policy rules.

package dpp.authz

import future.keywords.if
import future.keywords.in

tenant_match if {
    not input.resource.tenant_id
}

tenant_match if {
    input.resource.tenant_id == input.subject.tenant_id
}

is_owner if {
    input.resource.owner_subject == input.subject.sub
}

is_shared if {
    input.resource.shared_with_current_user == true
}

is_tenant_visible if {
    input.resource.visibility_scope == "tenant"
}

is_owner_team_accessible if {
    is_owner
}

is_owner_team_accessible if {
    is_shared
}

is_owner_team_accessible if {
    is_tenant_visible
}

consumer_allowed := {
    "https://admin-shell.io/idta/nameplate",
    "https://admin-shell.io/zvei/nameplate",
    "0173-1#01-AHX837#002",
    "https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2",
    "https://admin-shell.io/idta/TechnicalData",
    "https://admin-shell.io/idta/CarbonFootprint",
    "https://admin-shell.io/idta/BatteryPassport",
}

recycler_allowed := consumer_allowed

semantic_id_allowed(allowed_set) if {
    some prefix in allowed_set
    startswith(input.resource.semantic_id, prefix)
}
