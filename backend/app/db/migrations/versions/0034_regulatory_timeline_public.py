"""Add public regulatory timeline snapshots table

Revision ID: 0034_regulatory_timeline_public
Revises: 0033_cirpass_lab_events
Create Date: 2026-02-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0034_regulatory_timeline_public"
down_revision = "0033_cirpass_lab_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "regulatory_timeline_snapshots",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuid_generate_v7()"),
            primary_key=True,
        ),
        sa.Column("events_json", JSONB(), nullable=False),
        sa.Column("digest_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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

    op.create_index(
        "ix_regulatory_timeline_snapshot_fetched_at",
        "regulatory_timeline_snapshots",
        ["fetched_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_regulatory_timeline_snapshot_fetched_at",
        table_name="regulatory_timeline_snapshots",
    )
    op.drop_table("regulatory_timeline_snapshots")
