"""Complete tenant row-level security for tables added in migrations 0008-0021

Revision ID: 0022_complete_tenant_rls
Revises: 0021_verifiable_credentials
Create Date: 2026-02-08
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0022_complete_tenant_rls"
down_revision = "0021_verifiable_credentials"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "dpp_masters",
    "dpp_master_versions",
    "dpp_master_aliases",
    "audit_merkle_roots",
    "compliance_reports",
    "edc_asset_registrations",
    "thread_events",
    "lca_calculations",
    "epcis_events",
    "epcis_named_queries",
    "webhook_subscriptions",
    "resolver_links",
    "shell_descriptors",
    "asset_discovery_mappings",
    "issued_credentials",
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
