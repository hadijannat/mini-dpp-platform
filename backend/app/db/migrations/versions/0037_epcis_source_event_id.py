"""Add source_event_id column with partial unique index for EPCIS idempotency.

Revision ID: 0037epcissourceeventid
Revises: 0036_ds_publication_jobs
Create Date: 2026-02-19
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "0037epcissourceeventid"
down_revision = "0036_ds_publication_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "epcis_events",
        sa.Column("source_event_id", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_epcis_events_source_event_id_unique",
        "epcis_events",
        ["tenant_id", "source_event_id"],
        unique=True,
        postgresql_where=sa.text("source_event_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_epcis_events_source_event_id_unique", table_name="epcis_events")
    op.drop_column("epcis_events", "source_event_id")
