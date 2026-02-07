"""Create edc_asset_registrations table and add 'edc' to connectortype enum

Revision ID: 0013_edc_tables
Revises: 0012_compliance_tables
Create Date: 2026-02-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0013_edc_tables"
down_revision = "0012_compliance_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add 'edc' to the connectortype enum
    op.execute("ALTER TYPE connectortype ADD VALUE IF NOT EXISTS 'edc'")

    # Create edc_asset_registrations table
    op.create_table(
        "edc_asset_registrations",
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
            "dpp_id",
            sa.Uuid(),
            sa.ForeignKey("dpps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connector_id",
            sa.Uuid(),
            sa.ForeignKey("connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "edc_asset_id",
            sa.String(255),
            nullable=False,
            comment="Asset ID in EDC catalog",
        ),
        sa.Column(
            "edc_policy_id",
            sa.String(255),
            nullable=True,
            comment="Policy definition ID in EDC",
        ),
        sa.Column(
            "edc_contract_id",
            sa.String(255),
            nullable=True,
            comment="Contract definition ID in EDC",
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="registered",
            comment="Registration status: registered, active, removed",
        ),
        sa.Column(
            "metadata",
            JSONB(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_edc_registrations_tenant_dpp",
        "edc_asset_registrations",
        ["tenant_id", "dpp_id"],
    )
    op.create_index(
        "ix_edc_registrations_connector",
        "edc_asset_registrations",
        ["connector_id"],
    )
    op.create_index(
        "ix_edc_registrations_asset",
        "edc_asset_registrations",
        ["edc_asset_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_edc_registrations_asset",
        table_name="edc_asset_registrations",
    )
    op.drop_index(
        "ix_edc_registrations_connector",
        table_name="edc_asset_registrations",
    )
    op.drop_index(
        "ix_edc_registrations_tenant_dpp",
        table_name="edc_asset_registrations",
    )
    op.drop_table("edc_asset_registrations")

    # Note: PostgreSQL does not support removing values from an enum type.
    # The 'edc' value will remain in the connectortype enum after downgrade.
