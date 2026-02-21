"""Add CEN data carrier binding and quality-check support.

Revision ID: 0043_cen_carrier_qa_and_binding
Revises: 0042_cen_operator_facility
Create Date: 2026-02-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0043_cen_carrier_qa_and_binding"
down_revision = "0042_cen_operator_facility"
branch_labels = None
depends_on = None


def _enable_tenant_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table_name}_tenant_isolation
        ON {table_name}
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """
    )


def _disable_tenant_rls(table_name: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name}")
    op.execute(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.add_column(
        "data_carriers",
        sa.Column(
            "external_identifier_id",
            sa.UUID(),
            sa.ForeignKey("external_identifiers.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "data_carriers",
        sa.Column("payload_sha256", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_data_carriers_external_identifier_id",
        "data_carriers",
        ["external_identifier_id"],
    )

    op.create_table(
        "data_carrier_quality_checks",
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
        sa.Column("check_type", sa.String(length=64), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("performed_by_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "performed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_data_carrier_quality_checks_carrier_id",
        "data_carrier_quality_checks",
        ["carrier_id"],
    )
    op.create_index(
        "ix_data_carrier_quality_checks_check_type",
        "data_carrier_quality_checks",
        ["check_type"],
    )
    op.create_index(
        "ix_data_carrier_quality_checks_performed_at",
        "data_carrier_quality_checks",
        ["performed_at"],
    )
    _enable_tenant_rls("data_carrier_quality_checks")


def downgrade() -> None:
    _disable_tenant_rls("data_carrier_quality_checks")

    op.drop_index(
        "ix_data_carrier_quality_checks_performed_at",
        table_name="data_carrier_quality_checks",
    )
    op.drop_index(
        "ix_data_carrier_quality_checks_check_type",
        table_name="data_carrier_quality_checks",
    )
    op.drop_index(
        "ix_data_carrier_quality_checks_carrier_id",
        table_name="data_carrier_quality_checks",
    )
    op.drop_table("data_carrier_quality_checks")

    op.drop_index("ix_data_carriers_external_identifier_id", table_name="data_carriers")
    op.drop_column("data_carriers", "payload_sha256")
    op.drop_column("data_carriers", "external_identifier_id")
