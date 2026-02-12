"""Add dataspace control-plane tables and enums

Revision ID: 0028_dataspace_control_plane
Revises: 0027_dpp_attachments
Create Date: 2026-02-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0028_dataspace_control_plane"
down_revision = "0027_dpp_attachments"
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
    sa.Enum("edc", "catena_x_dtr", name="dataspaceconnectorruntime").create(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum(
        "draft",
        "approved",
        "active",
        "superseded",
        name="dataspacepolicytemplatestate",
    ).create(op.get_bind(), checkfirst=True)
    sa.Enum("queued", "running", "passed", "failed", name="dataspacerunstatus").create(
        op.get_bind(),
        checkfirst=True,
    )

    op.create_table(
        "dataspace_connectors",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "runtime",
            postgresql.ENUM(
                "edc",
                "catena_x_dtr",
                name="dataspaceconnectorruntime",
                create_type=False,
            ),
            nullable=False,
            server_default="edc",
        ),
        sa.Column("participant_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active",
                "disabled",
                "error",
                name="connectorstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="disabled",
        ),
        sa.Column("runtime_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_validation_result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_dataspace_connectors_tenant_name"),
    )
    op.create_index(
        "ix_dataspace_connectors_runtime",
        "dataspace_connectors",
        ["runtime"],
    )
    op.create_index(
        "ix_dataspace_connectors_status",
        "dataspace_connectors",
        ["status"],
    )

    op.create_table(
        "dataspace_connector_secrets",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "connector_id",
            sa.UUID(),
            sa.ForeignKey("dataspace_connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("secret_ref", sa.String(length=255), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "connector_id",
            "secret_ref",
            name="uq_dataspace_connector_secret_ref",
        ),
    )
    op.create_index(
        "ix_dataspace_connector_secrets_connector",
        "dataspace_connector_secrets",
        ["connector_id"],
    )

    op.create_table(
        "dataspace_policy_templates",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False, server_default="1"),
        sa.Column(
            "state",
            postgresql.ENUM(
                "draft",
                "approved",
                "active",
                "superseded",
                name="dataspacepolicytemplatestate",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column("approved_by_subject", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "name",
            "version",
            name="uq_dataspace_policy_templates_tenant_name_version",
        ),
    )
    op.create_index(
        "ix_dataspace_policy_templates_state",
        "dataspace_policy_templates",
        ["state"],
    )

    op.create_table(
        "dataspace_asset_publications",
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
            "connector_id",
            sa.UUID(),
            sa.ForeignKey("dataspace_connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "policy_template_id",
            sa.UUID(),
            sa.ForeignKey("dataspace_policy_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "revision_id",
            sa.UUID(),
            sa.ForeignKey("dpp_revisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("asset_id", sa.String(length=255), nullable=False),
        sa.Column("access_policy_id", sa.String(length=255), nullable=True),
        sa.Column("usage_policy_id", sa.String(length=255), nullable=True),
        sa.Column("contract_definition_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="published"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_dataspace_asset_publications_idempotency",
        ),
    )
    op.create_index(
        "ix_dataspace_asset_publications_dpp",
        "dataspace_asset_publications",
        ["tenant_id", "dpp_id"],
    )
    op.create_index(
        "ix_dataspace_asset_publications_connector",
        "dataspace_asset_publications",
        ["connector_id"],
    )
    op.create_index(
        "ix_dataspace_asset_publications_asset",
        "dataspace_asset_publications",
        ["asset_id"],
    )

    op.create_table(
        "dataspace_negotiations",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "connector_id",
            sa.UUID(),
            sa.ForeignKey("dataspace_connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "publication_id",
            sa.UUID(),
            sa.ForeignKey("dataspace_asset_publications.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("negotiation_id", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("contract_agreement_id", sa.String(length=255), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_dataspace_negotiations_idempotency",
        ),
    )
    op.create_index(
        "ix_dataspace_negotiations_connector",
        "dataspace_negotiations",
        ["connector_id"],
    )
    op.create_index(
        "ix_dataspace_negotiations_external_id",
        "dataspace_negotiations",
        ["negotiation_id"],
    )

    op.create_table(
        "dataspace_transfers",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "connector_id",
            sa.UUID(),
            sa.ForeignKey("dataspace_connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "negotiation_id",
            sa.UUID(),
            sa.ForeignKey("dataspace_negotiations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("transfer_id", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("data_destination", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_dataspace_transfers_idempotency",
        ),
    )
    op.create_index("ix_dataspace_transfers_connector", "dataspace_transfers", ["connector_id"])
    op.create_index(
        "ix_dataspace_transfers_external_id",
        "dataspace_transfers",
        ["transfer_id"],
    )

    op.create_table(
        "dataspace_conformance_runs",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "connector_id",
            sa.UUID(),
            sa.ForeignKey("dataspace_connectors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("run_type", sa.String(length=64), nullable=False, server_default="dsp-tck"),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued",
                "running",
                "passed",
                "failed",
                name="dataspacerunstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("artifact_url", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dataspace_conformance_runs_tenant_created",
        "dataspace_conformance_runs",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_dataspace_conformance_runs_status",
        "dataspace_conformance_runs",
        ["status"],
    )

    for table_name in (
        "dataspace_connectors",
        "dataspace_connector_secrets",
        "dataspace_policy_templates",
        "dataspace_asset_publications",
        "dataspace_negotiations",
        "dataspace_transfers",
        "dataspace_conformance_runs",
    ):
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in (
        "dataspace_conformance_runs",
        "dataspace_transfers",
        "dataspace_negotiations",
        "dataspace_asset_publications",
        "dataspace_policy_templates",
        "dataspace_connector_secrets",
        "dataspace_connectors",
    ):
        _disable_tenant_rls(table_name)

    op.drop_index("ix_dataspace_conformance_runs_status", table_name="dataspace_conformance_runs")
    op.drop_index(
        "ix_dataspace_conformance_runs_tenant_created",
        table_name="dataspace_conformance_runs",
    )
    op.drop_table("dataspace_conformance_runs")

    op.drop_index("ix_dataspace_transfers_external_id", table_name="dataspace_transfers")
    op.drop_index("ix_dataspace_transfers_connector", table_name="dataspace_transfers")
    op.drop_table("dataspace_transfers")

    op.drop_index("ix_dataspace_negotiations_external_id", table_name="dataspace_negotiations")
    op.drop_index("ix_dataspace_negotiations_connector", table_name="dataspace_negotiations")
    op.drop_table("dataspace_negotiations")

    op.drop_index(
        "ix_dataspace_asset_publications_asset",
        table_name="dataspace_asset_publications",
    )
    op.drop_index(
        "ix_dataspace_asset_publications_connector",
        table_name="dataspace_asset_publications",
    )
    op.drop_index(
        "ix_dataspace_asset_publications_dpp",
        table_name="dataspace_asset_publications",
    )
    op.drop_table("dataspace_asset_publications")

    op.drop_index("ix_dataspace_policy_templates_state", table_name="dataspace_policy_templates")
    op.drop_table("dataspace_policy_templates")

    op.drop_index(
        "ix_dataspace_connector_secrets_connector",
        table_name="dataspace_connector_secrets",
    )
    op.drop_table("dataspace_connector_secrets")

    op.drop_index("ix_dataspace_connectors_status", table_name="dataspace_connectors")
    op.drop_index("ix_dataspace_connectors_runtime", table_name="dataspace_connectors")
    op.drop_table("dataspace_connectors")

    sa.Enum("queued", "running", "passed", "failed", name="dataspacerunstatus").drop(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum(
        "draft",
        "approved",
        "active",
        "superseded",
        name="dataspacepolicytemplatestate",
    ).drop(op.get_bind(), checkfirst=True)
    sa.Enum("edc", "catena_x_dtr", name="dataspaceconnectorruntime").drop(
        op.get_bind(),
        checkfirst=True,
    )
