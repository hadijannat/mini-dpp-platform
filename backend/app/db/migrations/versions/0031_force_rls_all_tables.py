"""Add FORCE ROW LEVEL SECURITY to all tenant-scoped tables

Without FORCE, the table owner (the PostgreSQL role that owns the tables)
is exempt from all RLS policies. This migration ensures that even the
table owner is subject to tenant isolation policies, closing the gap
where application-level queries running as the table owner would bypass
RLS entirely.

Tables role_upgrade_requests (0024) and dpp_attachments (0027) already
have FORCE RLS and are excluded.

Revision ID: 0031_force_rls_all_tables
Revises: 0030_dpp_revision_manifests
Create Date: 2026-02-13
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0031_force_rls_all_tables"
down_revision = "0030_dpp_revision_manifests"
branch_labels = None
depends_on = None

# All tenant-scoped tables that have ENABLE RLS but not FORCE RLS.
# Ordered by migration that originally enabled RLS.
_TABLES = (
    # 0005_tenant_rls
    "dpps",
    "dpp_revisions",
    "encrypted_values",
    "policies",
    "connectors",
    "audit_events",
    # 0008_dpp_masters
    "dpp_masters",
    "dpp_master_versions",
    # 0009_master_aliases_semver
    "dpp_master_aliases",
    # 0022_complete_tenant_rls
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
    # 0025_ownership_visibility_access
    "resource_shares",
    "batch_import_jobs",
    "batch_import_job_items",
    # 0028_dataspace_control_plane
    "dataspace_connectors",
    "dataspace_connector_secrets",
    "dataspace_policy_templates",
    "dataspace_asset_publications",
    "dataspace_negotiations",
    "dataspace_transfers",
    "dataspace_conformance_runs",
    # 0029_data_carriers
    "data_carriers",
    "data_carrier_artifacts",
)


def upgrade() -> None:
    for table_name in _TABLES:
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table_name in _TABLES:
        op.execute(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY")
