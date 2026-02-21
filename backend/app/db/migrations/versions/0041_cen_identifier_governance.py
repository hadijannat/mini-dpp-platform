"""Add CEN identifier governance tables and seed baseline schemes.

Revision ID: 0041_cen_identifier_governance
Revises: 0040_crypto_hardening
Create Date: 2026-02-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0041_cen_identifier_governance"
down_revision = "0040_crypto_hardening"
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
    sa.Enum("product", "operator", "facility", name="identifierentitytype").create(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum("issuing_agency", "self_issued", "hybrid", name="identifierissuancemodel").create(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum("active", "deprecated", "withdrawn", name="externalidentifierstatus").create(
        op.get_bind(),
        checkfirst=True,
    )

    op.create_table(
        "identifier_schemes",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column(
            "entity_type",
            postgresql.ENUM(
                "product",
                "operator",
                "facility",
                name="identifierentitytype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "issuance_model",
            postgresql.ENUM(
                "issuing_agency",
                "self_issued",
                "hybrid",
                name="identifierissuancemodel",
                create_type=False,
            ),
            nullable=False,
            server_default="self_issued",
        ),
        sa.Column("canonicalization_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("openness_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_identifier_schemes_code"),
    )
    op.create_index("ix_identifier_schemes_entity_type", "identifier_schemes", ["entity_type"])
    op.create_index(
        "ix_identifier_schemes_issuance_model",
        "identifier_schemes",
        ["issuance_model"],
    )

    op.create_table(
        "external_identifiers",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "entity_type",
            postgresql.ENUM(
                "product",
                "operator",
                "facility",
                name="identifierentitytype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "scheme_code",
            sa.String(length=64),
            sa.ForeignKey("identifier_schemes.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("value_raw", sa.Text(), nullable=False),
        sa.Column("value_canonical", sa.Text(), nullable=False),
        sa.Column(
            "granularity",
            postgresql.ENUM("model", "batch", "item", name="datacarrieridentitylevel", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active",
                "deprecated",
                "withdrawn",
                name="externalidentifierstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "replaced_by_identifier_id",
            sa.UUID(),
            sa.ForeignKey("external_identifiers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deprecates_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scheme_code",
            "value_canonical",
            name="uq_external_identifiers_scheme_value",
        ),
    )
    op.create_index("ix_external_identifiers_entity_type", "external_identifiers", ["entity_type"])
    op.create_index("ix_external_identifiers_status", "external_identifiers", ["status"])

    op.create_table(
        "dpp_identifiers",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("dpp_id", sa.UUID(), sa.ForeignKey("dpps.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "external_identifier_id",
            sa.UUID(),
            sa.ForeignKey("external_identifiers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dpp_id", "external_identifier_id", name="uq_dpp_identifier_link"),
    )
    op.create_index("ix_dpp_identifiers_dpp", "dpp_identifiers", ["dpp_id"])
    op.create_index(
        "ix_dpp_identifiers_external_identifier",
        "dpp_identifiers",
        ["external_identifier_id"],
    )

    for table_name in ("external_identifiers", "dpp_identifiers"):
        _enable_tenant_rls(table_name)

    op.execute(
        """
        INSERT INTO identifier_schemes (
            code, entity_type, issuance_model, canonicalization_rules, validation_rules, openness_metadata
        )
        VALUES
            (
                'gs1_gtin', 'product', 'issuing_agency',
                '{"digits_only": true, "trim": true}',
                '{"gtin_check_digit": true}',
                '{"resolver": "gs1_digital_link"}'
            ),
            (
                'iec61406', 'product', 'hybrid',
                '{"uri_normalization": true, "trim": true}',
                '{"required_fields": ["manufacturer_part_id"]}',
                '{"resolver": "iec61406_identification_link"}'
            ),
            (
                'direct_url', 'product', 'self_issued',
                '{"uri_normalization": true, "trim": true}',
                '{"allowed_schemes": ["https", "http"]}',
                '{"resolver": "direct"}'
            ),
            (
                'uri', 'operator', 'self_issued',
                '{"uri_normalization": true, "trim": true}',
                '{"allowed_schemes": ["https", "http"]}',
                '{"resolver": "external"}'
            ),
            (
                'gln', 'facility', 'issuing_agency',
                '{"digits_only": true, "trim": true}',
                '{"length": [13]}',
                '{"resolver": "gs1"}'
            ),
            (
                'eori', 'operator', 'issuing_agency',
                '{"uppercase": true, "trim": true}',
                '{"min_length": 8}',
                '{"resolver": "eu_customs"}'
            )
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    for table_name in ("dpp_identifiers", "external_identifiers"):
        _disable_tenant_rls(table_name)

    op.drop_index("ix_dpp_identifiers_external_identifier", table_name="dpp_identifiers")
    op.drop_index("ix_dpp_identifiers_dpp", table_name="dpp_identifiers")
    op.drop_table("dpp_identifiers")

    op.drop_index("ix_external_identifiers_status", table_name="external_identifiers")
    op.drop_index("ix_external_identifiers_entity_type", table_name="external_identifiers")
    op.drop_table("external_identifiers")

    op.drop_index("ix_identifier_schemes_issuance_model", table_name="identifier_schemes")
    op.drop_index("ix_identifier_schemes_entity_type", table_name="identifier_schemes")
    op.drop_table("identifier_schemes")

    sa.Enum("active", "deprecated", "withdrawn", name="externalidentifierstatus").drop(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum("issuing_agency", "self_issued", "hybrid", name="identifierissuancemodel").drop(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum("product", "operator", "facility", name="identifierentitytype").drop(
        op.get_bind(),
        checkfirst=True,
    )
