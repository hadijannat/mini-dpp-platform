"""Repair admin bypass role grants for schema/table access.

Revision ID: 0026_admin_bypass_grants_repair
Revises: 0025_ownership_visibility_access
Create Date: 2026-02-11
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0026_admin_bypass_grants_repair"
down_revision = "0025_ownership_visibility_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dpp_admin_bypass') THEN
                GRANT USAGE ON SCHEMA public TO dpp_admin_bypass;
                GRANT SELECT, INSERT, UPDATE, DELETE
                    ON ALL TABLES IN SCHEMA public TO dpp_admin_bypass;
                GRANT USAGE, SELECT, UPDATE
                    ON ALL SEQUENCES IN SCHEMA public TO dpp_admin_bypass;

                -- Ensure future tables/sequences created by app migrations are visible too.
                ALTER DEFAULT PRIVILEGES IN SCHEMA public
                    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO dpp_admin_bypass;
                ALTER DEFAULT PRIVILEGES IN SCHEMA public
                    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO dpp_admin_bypass;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # Intentionally left as no-op: this is a defensive repair migration.
    pass
