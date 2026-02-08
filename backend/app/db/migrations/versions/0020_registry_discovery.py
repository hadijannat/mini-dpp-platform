"""Create shell_descriptors and asset_discovery_mappings tables

Revision ID: 0020_registry_discovery
Revises: 0019_resolver_links
Create Date: 2026-02-08
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0020_registry_discovery"
down_revision = "0019_resolver_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- shell_descriptors ----
    op.create_table(
        "shell_descriptors",
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
        ),
        sa.Column("aas_id", sa.String(1024), nullable=False),
        sa.Column("id_short", sa.String(255), server_default="", nullable=False),
        sa.Column("global_asset_id", sa.String(1024), server_default="", nullable=False),
        sa.Column(
            "specific_asset_ids",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "submodel_descriptors",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "dpp_id",
            sa.Uuid(),
            sa.ForeignKey("dpps.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_by_subject", sa.String(255), nullable=False),
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
    # tenant_id index is auto-created by TenantScopedMixin (index=True)
    op.create_index(
        "ix_shell_descriptors_specific_asset_ids",
        "shell_descriptors",
        ["specific_asset_ids"],
        postgresql_using="gin",
    )
    op.create_index("ix_shell_descriptors_dpp_id", "shell_descriptors", ["dpp_id"])
    op.create_unique_constraint(
        "uq_shell_descriptors_tenant_aas_id",
        "shell_descriptors",
        ["tenant_id", "aas_id"],
    )

    # ---- asset_discovery_mappings ----
    op.create_table(
        "asset_discovery_mappings",
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
        ),
        sa.Column("asset_id_key", sa.String(255), nullable=False),
        sa.Column("asset_id_value", sa.String(1024), nullable=False),
        sa.Column("aas_id", sa.String(1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_asset_discovery_tenant_key_value",
        "asset_discovery_mappings",
        ["tenant_id", "asset_id_key", "asset_id_value"],
    )
    op.create_unique_constraint(
        "uq_asset_discovery_tenant_key_value_aas",
        "asset_discovery_mappings",
        ["tenant_id", "asset_id_key", "asset_id_value", "aas_id"],
    )


def downgrade() -> None:
    op.drop_table("asset_discovery_mappings")
    op.drop_table("shell_descriptors")
