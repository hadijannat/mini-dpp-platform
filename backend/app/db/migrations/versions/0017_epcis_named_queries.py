"""Create epcis_named_queries table for saved EPCIS query definitions

Revision ID: 0017_epcis_named_queries
Revises: 0016_epcis_events
Create Date: 2026-02-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0017_epcis_named_queries"
down_revision = "0016_epcis_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "epcis_named_queries",
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
            "name",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "query_params",
            JSONB(),
            nullable=False,
        ),
        sa.Column(
            "created_by_subject",
            sa.String(255),
            nullable=False,
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
        sa.UniqueConstraint("tenant_id", "name", name="uq_epcis_named_queries_tenant_name"),
    )


def downgrade() -> None:
    op.drop_table("epcis_named_queries")
