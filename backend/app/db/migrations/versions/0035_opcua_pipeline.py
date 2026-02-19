"""Add OPC UA ingestion pipeline tables

Revision ID: 0035_opcua_pipeline
Revises: 0034_regulatory_timeline_public
Create Date: 2026-02-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0035_opcua_pipeline"
down_revision = "0034_regulatory_timeline_public"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Create enums
    # ------------------------------------------------------------------
    opcua_auth_type = sa.Enum(
        "anonymous",
        "username_password",
        "certificate",
        name="opcuaauthtype",
    )
    opcua_auth_type.create(op.get_bind(), checkfirst=True)

    opcua_conn_status = sa.Enum(
        "disabled",
        "healthy",
        "degraded",
        "error",
        name="opcuaconnectionstatus",
    )
    opcua_conn_status.create(op.get_bind(), checkfirst=True)

    opcua_mapping_type = sa.Enum(
        "aas_patch",
        "epcis_event",
        name="opcuamappingtype",
    )
    opcua_mapping_type.create(op.get_bind(), checkfirst=True)

    dpp_binding_mode = sa.Enum(
        "by_dpp_id",
        "by_asset_ids",
        "by_serial_scan",
        name="dppbindingmode",
    )
    dpp_binding_mode.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # opcua_sources
    # ------------------------------------------------------------------
    op.create_table(
        "opcua_sources",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuid_generate_v7()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "endpoint_url",
            sa.Text(),
            nullable=False,
            comment="OPC UA endpoint URL, e.g. opc.tcp://host:4840",
        ),
        sa.Column(
            "security_policy",
            sa.String(100),
            nullable=True,
            comment="e.g. Basic256Sha256",
        ),
        sa.Column(
            "security_mode",
            sa.String(50),
            nullable=True,
            comment="e.g. SignAndEncrypt",
        ),
        sa.Column(
            "auth_type",
            postgresql.ENUM(
                "anonymous",
                "username_password",
                "certificate",
                name="opcuaauthtype",
                create_type=False,
            ),
            nullable=False,
            server_default="anonymous",
        ),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column(
            "password_encrypted",
            sa.Text(),
            nullable=True,
            comment="AES-256-GCM encrypted password (enc:v1: prefix)",
        ),
        sa.Column(
            "client_cert_ref",
            sa.Text(),
            nullable=True,
            comment="MinIO object key for client certificate",
        ),
        sa.Column(
            "client_key_ref",
            sa.Text(),
            nullable=True,
            comment="MinIO object key for client private key",
        ),
        sa.Column(
            "server_cert_pinned_sha256",
            sa.String(64),
            nullable=True,
            comment="Optional SHA-256 pin of server certificate",
        ),
        sa.Column(
            "connection_status",
            postgresql.ENUM(
                "disabled",
                "healthy",
                "degraded",
                "error",
                name="opcuaconnectionstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="disabled",
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            sa.String(255),
            nullable=False,
            comment="OIDC subject of creator",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_opcua_sources_status", "opcua_sources", ["connection_status"])
    op.create_index("ix_opcua_sources_endpoint", "opcua_sources", ["endpoint_url"])

    # ------------------------------------------------------------------
    # opcua_nodesets
    # ------------------------------------------------------------------
    op.create_table(
        "opcua_nodesets",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuid_generate_v7()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("opcua_sources.id", ondelete="SET NULL"),
            nullable=True,
            comment="Optional link to a source (standalone uploads allowed)",
        ),
        sa.Column("namespace_uri", sa.Text(), nullable=False),
        sa.Column("nodeset_version", sa.String(100), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("companion_spec_name", sa.String(255), nullable=True),
        sa.Column("companion_spec_version", sa.String(100), nullable=True),
        sa.Column(
            "nodeset_file_ref",
            sa.Text(),
            nullable=False,
            comment="MinIO object key for NodeSet2.xml",
        ),
        sa.Column(
            "companion_spec_file_ref",
            sa.Text(),
            nullable=True,
            comment="MinIO object key for companion spec PDF",
        ),
        sa.Column(
            "hash_sha256",
            sa.String(64),
            nullable=False,
            comment="SHA-256 of the uploaded NodeSet XML",
        ),
        sa.Column(
            "parsed_node_graph",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Full parsed node hierarchy for search and mapping",
        ),
        sa.Column(
            "parsed_summary_json",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Counts: objects, variables, datatypes, engineering units",
        ),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_opcua_nodesets_namespace",
        "opcua_nodesets",
        ["tenant_id", "namespace_uri"],
    )
    op.create_index(
        "ix_opcua_nodesets_node_graph",
        "opcua_nodesets",
        ["parsed_node_graph"],
        postgresql_using="gin",
    )

    # ------------------------------------------------------------------
    # opcua_mappings
    # ------------------------------------------------------------------
    op.create_table(
        "opcua_mappings",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuid_generate_v7()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("opcua_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "nodeset_id",
            sa.Uuid(),
            sa.ForeignKey("opcua_nodesets.id", ondelete="SET NULL"),
            nullable=True,
            comment="Optional link for validation context",
        ),
        sa.Column(
            "mapping_type",
            postgresql.ENUM(
                "aas_patch",
                "epcis_event",
                name="opcuamappingtype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "opcua_node_id",
            sa.Text(),
            nullable=False,
            comment="OPC UA NodeId, e.g. ns=4;s=Temperature",
        ),
        sa.Column(
            "opcua_browse_path",
            sa.Text(),
            nullable=True,
            comment="Human-readable browse path for display",
        ),
        sa.Column("opcua_datatype", sa.String(100), nullable=True),
        sa.Column(
            "sampling_interval_ms",
            sa.Integer(),
            nullable=True,
            comment="Override default sampling interval (ms)",
        ),
        # DPP binding
        sa.Column(
            "dpp_binding_mode",
            postgresql.ENUM(
                "by_dpp_id",
                "by_asset_ids",
                "by_serial_scan",
                name="dppbindingmode",
                create_type=False,
            ),
            nullable=False,
            server_default="by_dpp_id",
        ),
        sa.Column(
            "dpp_id",
            sa.Uuid(),
            sa.ForeignKey("dpps.id", ondelete="SET NULL"),
            nullable=True,
            comment="Target DPP when binding_mode=BY_DPP_ID",
        ),
        sa.Column(
            "asset_id_query",
            JSONB(),
            nullable=True,
            comment="Query for BY_ASSET_IDS mode, e.g. {gtin, serialNumber}",
        ),
        # AAS target
        sa.Column("target_template_key", sa.String(100), nullable=True),
        sa.Column("target_submodel_id", sa.Text(), nullable=True),
        sa.Column(
            "target_aas_path",
            sa.Text(),
            nullable=True,
            comment="Canonical patch path within AAS submodel",
        ),
        sa.Column(
            "patch_op",
            sa.String(50),
            nullable=True,
            comment="Canonical op: set_value, set_multilang, add_list_item, etc.",
        ),
        sa.Column(
            "value_transform_expr",
            sa.Text(),
            nullable=True,
            comment="Transform DSL expression, e.g. scale:0.001|round:2",
        ),
        sa.Column("unit_hint", sa.String(50), nullable=True),
        # SAMM metadata
        sa.Column(
            "samm_aspect_urn",
            sa.Text(),
            nullable=True,
            comment="Catena-X SAMM aspect model URN",
        ),
        sa.Column("samm_property", sa.String(255), nullable=True),
        sa.Column("samm_version", sa.String(50), nullable=True),
        # EPCIS metadata
        sa.Column("epcis_event_type", sa.String(50), nullable=True),
        sa.Column("epcis_biz_step", sa.Text(), nullable=True),
        sa.Column("epcis_disposition", sa.Text(), nullable=True),
        sa.Column("epcis_action", sa.String(20), nullable=True),
        sa.Column("epcis_read_point", sa.Text(), nullable=True),
        sa.Column("epcis_biz_location", sa.Text(), nullable=True),
        sa.Column(
            "epcis_source_event_id_template",
            sa.Text(),
            nullable=True,
            comment="Template for idempotent event ID generation",
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_opcua_mappings_source", "opcua_mappings", ["source_id"])
    op.create_index("ix_opcua_mappings_dpp", "opcua_mappings", ["dpp_id"])
    op.create_index("ix_opcua_mappings_type", "opcua_mappings", ["mapping_type"])

    # ------------------------------------------------------------------
    # opcua_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "opcua_jobs",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuid_generate_v7()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("opcua_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mapping_id",
            sa.Uuid(),
            sa.ForeignKey("opcua_mappings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="idle",
            comment="idle, subscribed, paused, error",
        ),
        sa.Column(
            "last_value_json",
            JSONB(),
            nullable=True,
            comment="Last received OPC UA value + quality + timestamp",
        ),
        sa.Column("last_flush_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_unique_constraint("uq_opcua_jobs_mapping", "opcua_jobs", ["mapping_id"])
    op.create_index("ix_opcua_jobs_source", "opcua_jobs", ["source_id"])

    # ------------------------------------------------------------------
    # opcua_deadletters
    # ------------------------------------------------------------------
    op.create_table(
        "opcua_deadletters",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuid_generate_v7()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "mapping_id",
            sa.Uuid(),
            sa.ForeignKey("opcua_mappings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "value_payload",
            JSONB(),
            nullable=True,
            comment="OPC UA value that failed to apply (may be redacted)",
        ),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_opcua_deadletters_mapping", "opcua_deadletters", ["mapping_id"])
    op.create_index("ix_opcua_deadletters_last_seen", "opcua_deadletters", ["last_seen_at"])

    # ------------------------------------------------------------------
    # opcua_inventory_snapshots
    # ------------------------------------------------------------------
    op.create_table(
        "opcua_inventory_snapshots",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuid_generate_v7()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("opcua_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_json",
            JSONB(),
            nullable=False,
            comment="Server browse results: namespaces, capabilities, node summary",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_opcua_snapshots_source", "opcua_inventory_snapshots", ["source_id"])

    # Enable Row Level Security on all tenant-scoped tables
    _opcua_rls_tables = [
        "opcua_sources",
        "opcua_nodesets",
        "opcua_mappings",
        "opcua_jobs",
        "opcua_deadletters",
        "opcua_inventory_snapshots",
    ]
    for table_name in _opcua_rls_tables:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table_name}_tenant_isolation
            ON {table_name}
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            """
        )


def downgrade() -> None:
    # Disable RLS on all tables (reverse order)
    _opcua_rls_tables = [
        "opcua_inventory_snapshots",
        "opcua_deadletters",
        "opcua_jobs",
        "opcua_mappings",
        "opcua_nodesets",
        "opcua_sources",
    ]
    for table_name in _opcua_rls_tables:
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name}")
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")

    # Drop tables in reverse dependency order
    op.drop_index("ix_opcua_snapshots_source", table_name="opcua_inventory_snapshots")
    op.drop_table("opcua_inventory_snapshots")

    op.drop_index("ix_opcua_deadletters_last_seen", table_name="opcua_deadletters")
    op.drop_index("ix_opcua_deadletters_mapping", table_name="opcua_deadletters")
    op.drop_table("opcua_deadletters")

    op.drop_constraint("uq_opcua_jobs_mapping", "opcua_jobs", type_="unique")
    op.drop_index("ix_opcua_jobs_source", table_name="opcua_jobs")
    op.drop_table("opcua_jobs")

    op.drop_index("ix_opcua_mappings_type", table_name="opcua_mappings")
    op.drop_index("ix_opcua_mappings_dpp", table_name="opcua_mappings")
    op.drop_index("ix_opcua_mappings_source", table_name="opcua_mappings")
    op.drop_table("opcua_mappings")

    op.drop_index("ix_opcua_nodesets_node_graph", table_name="opcua_nodesets")
    op.drop_index("ix_opcua_nodesets_namespace", table_name="opcua_nodesets")
    op.drop_table("opcua_nodesets")

    op.drop_index("ix_opcua_sources_endpoint", table_name="opcua_sources")
    op.drop_index("ix_opcua_sources_status", table_name="opcua_sources")
    op.drop_table("opcua_sources")

    # Drop enums
    sa.Enum(name="dppbindingmode").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="opcuamappingtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="opcuaconnectionstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="opcuaauthtype").drop(op.get_bind(), checkfirst=True)
