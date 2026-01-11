#!/usr/bin/env bash
set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8081}"
REALM="${KEYCLOAK_REALM:-dpp-platform}"
ADMIN_USER="${KEYCLOAK_ADMIN_USER:-admin}"
ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-change-me}"
TENANTS="${TENANTS:-default}"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required" >&2
  exit 1
fi

get_token() {
  curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
    -d "client_id=admin-cli" \
    -d "username=${ADMIN_USER}" \
    -d "password=${ADMIN_PASSWORD}" \
    -d "grant_type=password" | jq -r '.access_token'
}

token="$(get_token)"
if [[ -z "${token}" || "${token}" == "null" ]]; then
  echo "Failed to get admin token" >&2
  exit 1
fi

auth_header=("-H" "Authorization: Bearer ${token}")

get_role() {
  local role_name="$1"
  curl -s "${auth_header[@]}" "${KEYCLOAK_URL}/admin/realms/${REALM}/roles/${role_name}"
}

get_group_id_by_name() {
  local group_name="$1"
  curl -s "${auth_header[@]}" \
    "${KEYCLOAK_URL}/admin/realms/${REALM}/groups?search=${group_name}" \
    | jq -r --arg name "${group_name}" '.[] | select(.name == $name) | .id' | head -n1
}

create_group() {
  local group_name="$1"
  curl -s -o /dev/null -w "%{http_code}" \
    "${auth_header[@]}" \
    -H "Content-Type: application/json" \
    -X POST "${KEYCLOAK_URL}/admin/realms/${REALM}/groups" \
    -d "{\"name\": \"${group_name}\"}"
}

create_subgroup() {
  local parent_id="$1"
  local group_name="$2"
  curl -s -o /dev/null -w "%{http_code}" \
    "${auth_header[@]}" \
    -H "Content-Type: application/json" \
    -X POST "${KEYCLOAK_URL}/admin/realms/${REALM}/groups/${parent_id}/children" \
    -d "{\"name\": \"${group_name}\"}"
}

assign_realm_role_to_group() {
  local group_id="$1"
  local role_json="$2"
  curl -s -o /dev/null -w "%{http_code}" \
    "${auth_header[@]}" \
    -H "Content-Type: application/json" \
    -X POST "${KEYCLOAK_URL}/admin/realms/${REALM}/groups/${group_id}/role-mappings/realm" \
    -d "[${role_json}]"
}

role_viewer="$(get_role viewer)"
role_publisher="$(get_role publisher)"
role_tenant_admin="$(get_role tenant_admin)"

IFS=',' read -r -a tenants <<< "${TENANTS}"

for slug in "${tenants[@]}"; do
  slug="${slug// /}"
  if [[ -z "${slug}" ]]; then
    continue
  fi

  group_name="tenant:${slug}"
  group_id="$(get_group_id_by_name "${group_name}")"

  if [[ -z "${group_id}" ]]; then
    status="$(create_group "${group_name}")"
    if [[ "${status}" != "201" && "${status}" != "204" ]]; then
      echo "Failed to create group ${group_name} (status ${status})" >&2
      continue
    fi
    group_id="$(get_group_id_by_name "${group_name}")"
  fi

  if [[ -z "${group_id}" ]]; then
    echo "Unable to resolve group id for ${group_name}" >&2
    continue
  fi

  # Create subgroups for role-based membership
  for child in viewer publisher tenant_admin; do
    child_name="${child}"
    child_id="$(curl -s "${auth_header[@]}" "${KEYCLOAK_URL}/admin/realms/${REALM}/groups/${group_id}/children" | jq -r --arg name "${child_name}" '.[] | select(.name == $name) | .id' | head -n1)"
    if [[ -z "${child_id}" ]]; then
      status="$(create_subgroup "${group_id}" "${child_name}")"
      if [[ "${status}" != "201" && "${status}" != "204" ]]; then
        echo "Failed to create subgroup ${child_name} for ${group_name} (status ${status})" >&2
        continue
      fi
      child_id="$(curl -s "${auth_header[@]}" "${KEYCLOAK_URL}/admin/realms/${REALM}/groups/${group_id}/children" | jq -r --arg name "${child_name}" '.[] | select(.name == $name) | .id' | head -n1)"
    fi

    if [[ -n "${child_id}" ]]; then
      case "${child}" in
        viewer)
          assign_realm_role_to_group "${child_id}" "${role_viewer}" >/dev/null
          ;;
        publisher)
          assign_realm_role_to_group "${child_id}" "${role_publisher}" >/dev/null
          ;;
        tenant_admin)
          assign_realm_role_to_group "${child_id}" "${role_tenant_admin}" >/dev/null
          ;;
      esac
    fi
  done

  echo "Provisioned tenant groups for ${slug}"

done
