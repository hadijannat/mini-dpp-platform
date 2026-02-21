"""Add tenant-managed resolver domains and RFID carrier enums.

Revision ID: 0045_rfid_tenant_domains
Revises: 0044_cen_search_indexes
Create Date: 2026-02-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0045_rfid_tenant_domains"
down_revision = "0044_cen_search_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE datacarriertype ADD VALUE IF NOT EXISTS 'rfid'")
    op.execute("ALTER TYPE datacarrieridentifierscheme ADD VALUE IF NOT EXISTS 'gs1_epc_tds23'")

    sa.Enum("pending", "active", "disabled", name="tenantdomainstatus").create(
        op.get_bind(),
        checkfirst=True,
    )

    op.create_table(
        "tenant_domains",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "active",
                "disabled",
                name="tenantdomainstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verification_method", sa.String(length=32), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hostname", name="uq_tenant_domains_hostname"),
    )
    op.create_index("ix_tenant_domains_tenant_id", "tenant_domains", ["tenant_id"])
    op.create_index("ix_tenant_domains_status", "tenant_domains", ["status"])
    op.create_index(
        "uq_tenant_domains_one_active_primary",
        "tenant_domains",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("is_primary IS TRUE AND status = 'active'"),
    )

    # Tenant domains are tenant-scoped in authenticated flows and globally
    # readable in public resolver flows (before tenant context is known).
    op.execute("ALTER TABLE tenant_domains ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_domains FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_domains_tenant_isolation
        ON tenant_domains
        USING (
            current_setting('app.current_tenant', true) IS NULL
            OR tenant_id = current_setting('app.current_tenant', true)::uuid
        )
        """
    )

    op.execute(
        """
        INSERT INTO identifier_schemes (
            code, entity_type, issuance_model, canonicalization_rules, validation_rules, openness_metadata
        )
        VALUES (
            'gs1_epc_tds23', 'product', 'issuing_agency',
            '{"digital_link_uri_normalization": true, "trim": true}',
            '{"tds_version": "2.3", "supported_schemes": ["sgtin++"]}',
            '{"resolver": "gs1_digital_link", "transport": "rfid"}'
        )
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_domains_tenant_isolation ON tenant_domains")
    op.execute("ALTER TABLE tenant_domains NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_domains DISABLE ROW LEVEL SECURITY")

    op.drop_index("uq_tenant_domains_one_active_primary", table_name="tenant_domains")
    op.drop_index("ix_tenant_domains_status", table_name="tenant_domains")
    op.drop_index("ix_tenant_domains_tenant_id", table_name="tenant_domains")
    op.drop_table("tenant_domains")
    sa.Enum("pending", "active", "disabled", name="tenantdomainstatus").drop(
        op.get_bind(),
        checkfirst=True,
    )

    op.execute("DELETE FROM identifier_schemes WHERE code = 'gs1_epc_tds23'")

    # PostgreSQL enum values are intentionally not removed during downgrade.
