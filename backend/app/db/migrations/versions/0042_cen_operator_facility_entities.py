"""Add CEN operator/facility entities and identifier link tables.

Revision ID: 0042_cen_operator_facility
Revises: 0041_cen_identifier_governance
Create Date: 2026-02-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0042_cen_operator_facility"
down_revision = "0041_cen_identifier_governance"
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
    op.create_table(
        "economic_operators",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=8), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_economic_operators_tenant_name",
        "economic_operators",
        ["tenant_id", "legal_name"],
    )
    op.create_index("ix_economic_operators_country", "economic_operators", ["country"])

    op.create_table(
        "facilities",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "operator_id",
            sa.UUID(),
            sa.ForeignKey("economic_operators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("facility_name", sa.String(length=255), nullable=False),
        sa.Column("address", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facilities_operator", "facilities", ["operator_id"])
    op.create_index("ix_facilities_tenant_name", "facilities", ["tenant_id", "facility_name"])

    op.create_table(
        "operator_identifiers",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "operator_id",
            sa.UUID(),
            sa.ForeignKey("economic_operators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "external_identifier_id",
            sa.UUID(),
            sa.ForeignKey("external_identifiers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "operator_id",
            "external_identifier_id",
            name="uq_operator_identifier_link",
        ),
    )
    op.create_index("ix_operator_identifiers_operator", "operator_identifiers", ["operator_id"])
    op.create_index(
        "ix_operator_identifiers_external_identifier",
        "operator_identifiers",
        ["external_identifier_id"],
    )

    op.create_table(
        "facility_identifiers",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "facility_id",
            sa.UUID(),
            sa.ForeignKey("facilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "external_identifier_id",
            sa.UUID(),
            sa.ForeignKey("external_identifiers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "facility_id",
            "external_identifier_id",
            name="uq_facility_identifier_link",
        ),
    )
    op.create_index("ix_facility_identifiers_facility", "facility_identifiers", ["facility_id"])
    op.create_index(
        "ix_facility_identifiers_external_identifier",
        "facility_identifiers",
        ["external_identifier_id"],
    )

    for table_name in (
        "economic_operators",
        "facilities",
        "operator_identifiers",
        "facility_identifiers",
    ):
        _enable_tenant_rls(table_name)


def downgrade() -> None:
    for table_name in (
        "facility_identifiers",
        "operator_identifiers",
        "facilities",
        "economic_operators",
    ):
        _disable_tenant_rls(table_name)

    op.drop_index(
        "ix_facility_identifiers_external_identifier",
        table_name="facility_identifiers",
    )
    op.drop_index("ix_facility_identifiers_facility", table_name="facility_identifiers")
    op.drop_table("facility_identifiers")

    op.drop_index(
        "ix_operator_identifiers_external_identifier",
        table_name="operator_identifiers",
    )
    op.drop_index("ix_operator_identifiers_operator", table_name="operator_identifiers")
    op.drop_table("operator_identifiers")

    op.drop_index("ix_facilities_tenant_name", table_name="facilities")
    op.drop_index("ix_facilities_operator", table_name="facilities")
    op.drop_table("facilities")

    op.drop_index("ix_economic_operators_country", table_name="economic_operators")
    op.drop_index("ix_economic_operators_tenant_name", table_name="economic_operators")
    op.drop_table("economic_operators")
