#!/bin/bash
# Create a dedicated Keycloak database and user for production.
# Uses KEYCLOAK_DB_PASSWORD env var (passed from docker-compose).

set -e

KC_PASS="${KEYCLOAK_DB_PASSWORD:?KEYCLOAK_DB_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'keycloak') THEN
            CREATE ROLE keycloak LOGIN PASSWORD '${KC_PASS}';
        END IF;
    END
    \$\$;

    SELECT 'CREATE DATABASE keycloak OWNER keycloak'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')\gexec
EOSQL
