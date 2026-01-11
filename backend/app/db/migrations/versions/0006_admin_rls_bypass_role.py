"""Add admin RLS bypass role

Revision ID: 0006_admin_rls_bypass_role
Revises: 0005_tenant_rls
Create Date: 2026-01-11
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_admin_rls_bypass_role"
down_revision = "0005_tenant_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dpp_admin_bypass') THEN
                CREATE ROLE dpp_admin_bypass BYPASSRLS NOLOGIN;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dpp_user') THEN
                GRANT dpp_admin_bypass TO dpp_user;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dpp_user') THEN
                REVOKE dpp_admin_bypass FROM dpp_user;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dpp_admin_bypass') THEN
                DROP ROLE dpp_admin_bypass;
            END IF;
        END
        $$;
        """
    )
