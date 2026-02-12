# ABAC policy entrypoint with deterministic precedence across modular rule files.

package dpp.authz

import future.keywords.if
import future.keywords.in

default decision := {
    "effect": "deny",
    "reason": "No matching policy found"
}

decision := selected.decision if {
    priorities := [entry.priority | some entry in policy_candidate]
    count(priorities) > 0
    top_priority := min(priorities)
    some selected in policy_candidate
    selected.priority == top_priority
}
