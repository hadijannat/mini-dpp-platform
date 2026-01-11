"""Grant table privileges to admin bypass role

Revision ID: 0007_admin_bypass_privileges
Revises: 0006_admin_rls_bypass_role
Create Date: 2026-01-11
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0007_admin_bypass_privileges"
down_revision = "0006_admin_rls_bypass_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT USAGE ON SCHEMA public TO dpp_admin_bypass")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO dpp_admin_bypass"
    )
    op.execute("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO dpp_admin_bypass")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO dpp_admin_bypass"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO dpp_admin_bypass"
    )


def downgrade() -> None:
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE USAGE, SELECT, UPDATE ON SEQUENCES FROM dpp_admin_bypass"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM dpp_admin_bypass"
    )
    op.execute(
        "REVOKE USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public FROM dpp_admin_bypass"
    )
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM dpp_admin_bypass"
    )
    op.execute("REVOKE USAGE ON SCHEMA public FROM dpp_admin_bypass")
