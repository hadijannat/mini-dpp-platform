"""Add data carrier domain tables and resolver link management metadata

Revision ID: 0029_data_carriers
Revises: 0028_dataspace_control_plane
Create Date: 2026-02-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0029_data_carriers"
down_revision = "0028_dataspace_control_plane"
branch_labels = None
depends_on = None


def _enable_tenant_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table_name}_tenant_isolation
        ON {table_name}
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """
    )


def _disable_tenant_rls(table_name: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name}")
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    sa.Enum("model", "batch", "item", name="datacarrieridentitylevel").create(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum("gs1_gtin", "iec61406", "direct_url", name="datacarrieridentifierscheme").create(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum("qr", "datamatrix", "nfc", name="datacarriertype").create(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum(
        "dynamic_linkset",
        "direct_public_dpp",
        name="datacarrierresolverstrategy",
    ).create(op.get_bind(), checkfirst=True)
    sa.Enum("active", "deprecated", "withdrawn", name="datacarrierstatus").create(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum("png", "svg", "pdf", "zpl", "csv", name="datacarrierartifacttype").create(
        op.get_bind(),
        checkfirst=True,
    )

    op.create_table(
        "data_carriers",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "dpp_id", sa.UUID(), sa.ForeignKey("dpps.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "identity_level",
            postgresql.ENUM(
                "model",
                "batch",
                "item",
                name="datacarrieridentitylevel",
                create_type=False,
            ),
            nullable=False,
            server_default="item",
        ),
        sa.Column(
            "identifier_scheme",
            postgresql.ENUM(
                "gs1_gtin",
                "iec61406",
                "direct_url",
                name="datacarrieridentifierscheme",
                create_type=False,
            ),
            nullable=False,
            server_default="gs1_gtin",
        ),
        sa.Column(
            "carrier_type",
            postgresql.ENUM(
                "qr",
                "datamatrix",
                "nfc",
                name="datacarriertype",
                create_type=False,
            ),
            nullable=False,
            server_default="qr",
        ),
        sa.Column(
            "resolver_strategy",
            postgresql.ENUM(
                "dynamic_linkset",
                "direct_public_dpp",
                name="datacarrierresolverstrategy",
                create_type=False,
            ),
            nullable=False,
            server_default="dynamic_linkset",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active",
                "deprecated",
                "withdrawn",
                name="datacarrierstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("identifier_key", sa.String(length=512), nullable=False),
        sa.Column("identifier_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("encoded_uri", sa.Text(), nullable=False),
        sa.Column("layout_profile", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("placement_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pre_sale_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "is_gtin_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "replaced_by_carrier_id",
            sa.UUID(),
            sa.ForeignKey("data_carriers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("withdrawn_reason", sa.Text(), nullable=True),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_carriers_dpp_id", "data_carriers", ["dpp_id"])
    op.create_index("ix_data_carriers_status", "data_carriers", ["status"])
    op.create_index(
        "ix_data_carriers_identifier_scheme",
        "data_carriers",
        ["identifier_scheme"],
    )
    op.create_index(
        "ix_data_carriers_identifier_key",
        "data_carriers",
        ["identifier_key"],
    )
    op.create_index(
        "uq_data_carriers_tenant_identifier_active_like",
        "data_carriers",
        ["tenant_id", "identifier_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('active','deprecated')"),
    )

    op.create_table(
        "data_carrier_artifacts",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "carrier_id",
            sa.UUID(),
            sa.ForeignKey("data_carriers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "artifact_type",
            postgresql.ENUM(
                "png",
                "svg",
                "pdf",
                "zpl",
                "csv",
                name="datacarrierartifacttype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_data_carrier_artifacts_carrier_id",
        "data_carrier_artifacts",
        ["carrier_id"],
    )
    op.create_index(
        "ix_data_carrier_artifacts_artifact_type",
        "data_carrier_artifacts",
        ["artifact_type"],
    )

    op.add_column(
        "resolver_links",
        sa.Column(
            "managed_by_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "resolver_links",
        sa.Column(
            "source_data_carrier_id",
            sa.UUID(),
            sa.ForeignKey("data_carriers.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_resolver_links_source_data_carrier_id",
        "resolver_links",
        ["source_data_carrier_id"],
    )

    for table_name in ("data_carriers", "data_carrier_artifacts"):
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in ("data_carrier_artifacts", "data_carriers"):
        _disable_tenant_rls(table_name)

    op.drop_index(
        "ix_resolver_links_source_data_carrier_id",
        table_name="resolver_links",
    )
    op.drop_column("resolver_links", "source_data_carrier_id")
    op.drop_column("resolver_links", "managed_by_system")

    op.drop_index(
        "ix_data_carrier_artifacts_artifact_type",
        table_name="data_carrier_artifacts",
    )
    op.drop_index(
        "ix_data_carrier_artifacts_carrier_id",
        table_name="data_carrier_artifacts",
    )
    op.drop_table("data_carrier_artifacts")

    op.drop_index(
        "uq_data_carriers_tenant_identifier_active_like",
        table_name="data_carriers",
    )
    op.drop_index("ix_data_carriers_identifier_key", table_name="data_carriers")
    op.drop_index(
        "ix_data_carriers_identifier_scheme",
        table_name="data_carriers",
    )
    op.drop_index("ix_data_carriers_status", table_name="data_carriers")
    op.drop_index("ix_data_carriers_dpp_id", table_name="data_carriers")
    op.drop_table("data_carriers")

    sa.Enum("png", "svg", "pdf", "zpl", "csv", name="datacarrierartifacttype").drop(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum("active", "deprecated", "withdrawn", name="datacarrierstatus").drop(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum(
        "dynamic_linkset",
        "direct_public_dpp",
        name="datacarrierresolverstrategy",
    ).drop(op.get_bind(), checkfirst=True)
    sa.Enum("qr", "datamatrix", "nfc", name="datacarriertype").drop(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum("gs1_gtin", "iec61406", "direct_url", name="datacarrieridentifierscheme").drop(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum("model", "batch", "item", name="datacarrieridentitylevel").drop(
        op.get_bind(),
        checkfirst=True,
    )
