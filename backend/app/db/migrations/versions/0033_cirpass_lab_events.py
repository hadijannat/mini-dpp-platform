"""Add CIRPASS lab telemetry events table

Revision ID: 0033_cirpass_lab_events
Revises: 0032_cirpass_lab_public
Create Date: 2026-02-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0033_cirpass_lab_events"
down_revision = "0032_cirpass_lab_public"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cirpass_lab_events",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuid_generate_v7()"),
            primary_key=True,
        ),
        sa.Column("sid_hash", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("story_id", sa.String(length=64), nullable=False),
        sa.Column("step_id", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("variant", sa.String(length=32), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_cirpass_lab_event_latency",
        ),
    )

    op.create_index(
        "ix_cirpass_lab_events_sid_created",
        "cirpass_lab_events",
        ["sid_hash", "created_at"],
    )
    op.create_index(
        "ix_cirpass_lab_events_story_step",
        "cirpass_lab_events",
        ["story_id", "step_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cirpass_lab_events_story_step", table_name="cirpass_lab_events")
    op.drop_index("ix_cirpass_lab_events_sid_created", table_name="cirpass_lab_events")
    op.drop_table("cirpass_lab_events")
