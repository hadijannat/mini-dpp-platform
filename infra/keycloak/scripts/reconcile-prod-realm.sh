#!/usr/bin/env bash
set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-dpp-platform}"
ADMIN_USER="${KEYCLOAK_ADMIN_USER:-admin}"
ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-change-me}"
BACKEND_CLIENT_ID="${BACKEND_CLIENT_ID:-dpp-backend}"
KCADM_BIN="${KCADM_BIN:-/opt/keycloak/bin/kcadm.sh}"

if [[ ! -x "${KCADM_BIN}" ]]; then
  echo "kcadm.sh not found at ${KCADM_BIN}" >&2
  exit 1
fi

echo "Authenticating with Keycloak admin API..."
"${KCADM_BIN}" config credentials \
  --server "${KEYCLOAK_URL}" \
  --realm master \
  --user "${ADMIN_USER}" \
  --password "${ADMIN_PASSWORD}" >/dev/null

echo "Enforcing realm self-registration + verify-email flags..."
"${KCADM_BIN}" update "realms/${REALM}" \
  -s "registrationAllowed=true" \
  -s "verifyEmail=true" >/dev/null

service_account_username="service-account-${BACKEND_CLIENT_ID}"
service_account_id="$(
  "${KCADM_BIN}" get users -r "${REALM}" -q "username=${service_account_username}" \
    --fields id,username --format csv |
    tail -n +2 |
    cut -d',' -f1 |
    head -n1
)"

if [[ -z "${service_account_id}" ]]; then
  echo "Service account user '${service_account_username}' not found in realm '${REALM}'." >&2
  echo "Ensure client '${BACKEND_CLIENT_ID}' has serviceAccountsEnabled=true first." >&2
  exit 1
fi

echo "Reconciling realm-management roles for ${service_account_username}..."
for role in manage-users view-users query-users view-realm; do
  echo "Ensuring role '${role}' is assigned..."
  "${KCADM_BIN}" add-roles \
    -r "${REALM}" \
    --uid "${service_account_id}" \
    --cclientid realm-management \
    --rolename "${role}" >/dev/null
done

echo "Realm reconciliation complete."
echo "Current auth settings:"
"${KCADM_BIN}" get "realms/${REALM}" --fields realm,registrationAllowed,verifyEmail,smtpServer
