"""Enable tenant row-level security

Revision ID: 0005_tenant_rls
Revises: 0004_multi_tenancy
Create Date: 2026-01-11
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_tenant_rls"
down_revision = "0004_multi_tenancy"
branch_labels = None
depends_on = None


TENANT_TABLES = (
    "dpps",
    "dpp_revisions",
    "encrypted_values",
    "policies",
    "connectors",
    "audit_events",
)


def upgrade() -> None:
    for table_name in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table_name}_tenant_isolation
            ON {table_name}
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            """
        )


def downgrade() -> None:
    for table_name in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name}")
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")
