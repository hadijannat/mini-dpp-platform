"""Ensure every TenantScopedMixin model has a corresponding RLS policy."""

from app.db import models

# Tables with RLS from migration 0005
_RLS_0005 = {
    "dpps",
    "dpp_revisions",
    "encrypted_values",
    "policies",
    "connectors",
    "audit_events",
}

# Tables with RLS from migrations 0008/0009
_RLS_0008_0009 = {
    "dpp_masters",
    "dpp_master_versions",
    "dpp_master_aliases",
}

# Tables with RLS from migration 0022
_RLS_0022 = {
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
}

# Tables with RLS from migration 0024
_RLS_0024 = {
    "role_upgrade_requests",
}

# Tables with RLS from migration 0025
_RLS_0025 = {
    "resource_shares",
    "batch_import_jobs",
    "batch_import_job_items",
}

# Tables with RLS from migration 0027
_RLS_0027 = {
    "dpp_attachments",
}

# Tables with RLS from migration 0028
_RLS_0028 = {
    "dataspace_connectors",
    "dataspace_connector_secrets",
    "dataspace_policy_templates",
    "dataspace_asset_publications",
    "dataspace_negotiations",
    "dataspace_transfers",
    "dataspace_conformance_runs",
}

# Tables with RLS from migration 0029
_RLS_0029 = {
    "data_carriers",
    "data_carrier_artifacts",
}

# Tables with RLS from migration 0035
_RLS_0035 = {
    "opcua_sources",
    "opcua_nodesets",
    "opcua_mappings",
    "opcua_jobs",
    "opcua_deadletters",
    "opcua_inventory_snapshots",
}

# Tables with RLS from migration 0036
_RLS_0036 = {
    "dataspace_publication_jobs",
}

TABLES_WITH_RLS = (
    _RLS_0005
    | _RLS_0008_0009
    | _RLS_0022
    | _RLS_0024
    | _RLS_0025
    | _RLS_0027
    | _RLS_0028
    | _RLS_0029
    | _RLS_0035
    | _RLS_0036
)


def _tenant_scoped_tables() -> set[str]:
    """Introspect all ORM models using TenantScopedMixin."""
    tables: set[str] = set()
    for attr in dir(models):
        cls = getattr(models, attr)
        if (
            isinstance(cls, type)
            and issubclass(cls, models.TenantScopedMixin)
            and cls is not models.TenantScopedMixin
            and hasattr(cls, "__tablename__")
        ):
            tables.add(cls.__tablename__)
    return tables


class TestTenantRLSCoverage:
    def test_all_tenant_scoped_models_have_rls(self) -> None:
        """Every model with TenantScopedMixin must have a corresponding RLS policy."""
        tenant_tables = _tenant_scoped_tables()
        missing = tenant_tables - TABLES_WITH_RLS
        assert not missing, (
            f"TenantScopedMixin models missing RLS policies: {sorted(missing)}. "
            "Add them to the relevant migration and update TABLES_WITH_RLS in this test."
        )

    def test_no_stale_rls_entries(self) -> None:
        """TABLES_WITH_RLS should not contain tables that no longer exist."""
        tenant_tables = _tenant_scoped_tables()
        stale = TABLES_WITH_RLS - tenant_tables
        assert not stale, (
            f"TABLES_WITH_RLS contains tables not in ORM: {sorted(stale)}. "
            "Remove them from this test."
        )
