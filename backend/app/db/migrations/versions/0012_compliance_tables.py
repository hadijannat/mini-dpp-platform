"""Create compliance_reports table

Revision ID: 0012_compliance_tables
Revises: 0011_audit_crypto_columns
Create Date: 2026-02-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0012_compliance_tables"
down_revision = "0011_audit_crypto_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compliance_reports",
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
            "category",
            sa.String(100),
            nullable=False,
            comment="Product category (battery, textile, electronic, etc.)",
        ),
        sa.Column(
            "is_compliant",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "report_json",
            JSONB(),
            nullable=False,
            comment="Full compliance report payload",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_compliance_reports_tenant_dpp",
        "compliance_reports",
        ["tenant_id", "dpp_id"],
    )
    op.create_index(
        "ix_compliance_reports_category",
        "compliance_reports",
        ["category"],
    )


def downgrade() -> None:
    op.drop_index("ix_compliance_reports_category", table_name="compliance_reports")
    op.drop_index("ix_compliance_reports_tenant_dpp", table_name="compliance_reports")
    op.drop_table("compliance_reports")
