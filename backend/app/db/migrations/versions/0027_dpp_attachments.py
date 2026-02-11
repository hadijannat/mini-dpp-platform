"""Create dpp_attachments table

Revision ID: 0027_dpp_attachments
Revises: 0026_admin_bypass_grants_repair
Create Date: 2026-02-11
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0027_dpp_attachments"
down_revision = "0026_admin_bypass_grants_repair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dpp_attachments",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dpp_id", sa.UUID(), sa.ForeignKey("dpps.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "object_key", name="uq_dpp_attachment_object_key"),
    )

    op.create_index("ix_dpp_attachments_dpp_id", "dpp_attachments", ["dpp_id"])
    op.create_index(
        "ix_dpp_attachments_tenant_created",
        "dpp_attachments",
        ["tenant_id", "created_at"],
    )

    op.execute("ALTER TABLE dpp_attachments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE dpp_attachments FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_dpp_attachments
        ON dpp_attachments
        USING (tenant_id::text = current_setting('app.current_tenant', true))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_dpp_attachments ON dpp_attachments")
    op.execute("ALTER TABLE dpp_attachments DISABLE ROW LEVEL SECURITY")
    op.drop_table("dpp_attachments")
