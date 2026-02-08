"""Create issued_credentials table for W3C Verifiable Credentials

Revision ID: 0021_verifiable_credentials
Revises: 0020_registry_discovery
Create Date: 2026-02-08
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0021_verifiable_credentials"
down_revision = "0020_registry_discovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "issued_credentials",
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
        sa.Column(
            "dpp_id",
            sa.Uuid(),
            sa.ForeignKey("dpps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "credential_json",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column("issuer_did", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=False),
        sa.Column(
            "issuance_date",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expiration_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "revoked",
            sa.Boolean(),
            server_default="false",
            nullable=False,
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
    op.create_unique_constraint(
        "uq_issued_credentials_tenant_dpp",
        "issued_credentials",
        ["tenant_id", "dpp_id"],
    )
    # tenant_id index is auto-created by TenantScopedMixin (index=True)
    # but we need it in the migration since migration doesn't use ORM
    op.create_index(
        "ix_issued_credentials_tenant_id",
        "issued_credentials",
        ["tenant_id"],
    )
    op.create_index(
        "ix_issued_credentials_dpp_id",
        "issued_credentials",
        ["dpp_id"],
    )


def downgrade() -> None:
    op.drop_table("issued_credentials")
