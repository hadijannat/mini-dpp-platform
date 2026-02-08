"""Create resolver_links table for GS1 Digital Link resolution

Revision ID: 0019_resolver_links
Revises: 0018_webhooks
Create Date: 2026-02-08
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0019_resolver_links"
down_revision = "0018_webhooks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resolver_links",
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
        sa.Column("identifier", sa.String(512), nullable=False),
        sa.Column("link_type", sa.String(255), nullable=False),
        sa.Column("href", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(100), server_default="application/json", nullable=False),
        sa.Column("title", sa.String(500), server_default="", nullable=False),
        sa.Column("hreflang", sa.String(20), server_default="en", nullable=False),
        sa.Column("priority", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "dpp_id", sa.Uuid(), sa.ForeignKey("dpps.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
    op.create_index("ix_resolver_links_tenant", "resolver_links", ["tenant_id"])
    op.create_index("ix_resolver_links_identifier", "resolver_links", ["identifier"])
    op.create_index("ix_resolver_links_dpp_id", "resolver_links", ["dpp_id"])
    op.create_index("ix_resolver_links_link_type", "resolver_links", ["link_type"])
    op.create_index("ix_resolver_links_active", "resolver_links", ["active"])
    op.create_unique_constraint(
        "uq_resolver_links_tenant_identifier_type",
        "resolver_links",
        ["tenant_id", "identifier", "link_type"],
    )


def downgrade() -> None:
    op.drop_table("resolver_links")
