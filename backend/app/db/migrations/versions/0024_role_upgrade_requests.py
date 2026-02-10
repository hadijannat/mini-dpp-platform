"""Create role_upgrade_requests table

Revision ID: 0024_role_upgrade_requests
Revises: 0023_template_provenance
Create Date: 2026-02-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0024_role_upgrade_requests"
down_revision = "0023_template_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the rolerequeststatus enum
    sa.Enum("pending", "approved", "denied", name="rolerequeststatus").create(
        op.get_bind(), checkfirst=True
    )

    op.create_table(
        "role_upgrade_requests",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_subject", sa.String(255), nullable=False),
        sa.Column(
            "requested_role",
            postgresql.ENUM(
                "viewer", "publisher", "tenant_admin",
                name="tenantrole",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "approved", "denied",
                name="rolerequeststatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
    )

    op.create_index(
        "ix_role_upgrade_requests_tenant_user",
        "role_upgrade_requests",
        ["tenant_id", "user_subject"],
    )
    op.create_index(
        "ix_role_upgrade_requests_status",
        "role_upgrade_requests",
        ["status"],
    )

    # RLS policy (matches 0022 pattern)
    op.execute(
        "ALTER TABLE role_upgrade_requests ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE role_upgrade_requests FORCE ROW LEVEL SECURITY"
    )
    op.execute("""
        CREATE POLICY tenant_isolation_role_upgrade_requests
        ON role_upgrade_requests
        USING (tenant_id::text = current_setting('app.current_tenant', true))
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_role_upgrade_requests ON role_upgrade_requests")
    op.execute("ALTER TABLE role_upgrade_requests DISABLE ROW LEVEL SECURITY")
    op.drop_table("role_upgrade_requests")
    sa.Enum("pending", "approved", "denied", name="rolerequeststatus").drop(
        op.get_bind(), checkfirst=True
    )
