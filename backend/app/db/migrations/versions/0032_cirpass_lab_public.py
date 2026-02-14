"""Add public CIRPASS lab snapshots and leaderboard tables

Revision ID: 0032_cirpass_lab_public
Revises: 0031_force_rls_all_tables
Create Date: 2026-02-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0032_cirpass_lab_public"
down_revision = "0031_force_rls_all_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cirpass_story_snapshots",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuid_generate_v7()"),
            primary_key=True,
        ),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("zenodo_record_url", sa.Text(), nullable=False),
        sa.Column("zenodo_record_id", sa.String(length=64), nullable=True),
        sa.Column("stories_json", JSONB(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
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
        sa.UniqueConstraint(
            "version",
            "zenodo_record_url",
            name="uq_cirpass_snapshot_version_record",
        ),
    )
    op.create_index(
        "ix_cirpass_snapshot_fetched_at",
        "cirpass_story_snapshots",
        ["fetched_at"],
    )

    op.create_table(
        "cirpass_leaderboard_entries",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuid_generate_v7()"),
            primary_key=True,
        ),
        sa.Column("sid", sa.String(length=64), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("nickname", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("completion_seconds", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
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
        sa.CheckConstraint(
            "score >= 0",
            name="ck_cirpass_leaderboard_score_non_negative",
        ),
        sa.CheckConstraint(
            "completion_seconds >= 0",
            name="ck_cirpass_leaderboard_completion_non_negative",
        ),
        sa.UniqueConstraint(
            "sid",
            "version",
            name="uq_cirpass_leaderboard_sid_version",
        ),
    )

    op.create_index(
        "ix_cirpass_leaderboard_rank",
        "cirpass_leaderboard_entries",
        ["version", "score", "completion_seconds", "created_at"],
    )
    op.create_index(
        "ix_cirpass_leaderboard_sid_updated",
        "cirpass_leaderboard_entries",
        ["sid", "updated_at"],
    )
    op.create_index(
        "ix_cirpass_leaderboard_ip_updated",
        "cirpass_leaderboard_entries",
        ["ip_hash", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cirpass_leaderboard_ip_updated", table_name="cirpass_leaderboard_entries")
    op.drop_index("ix_cirpass_leaderboard_sid_updated", table_name="cirpass_leaderboard_entries")
    op.drop_index("ix_cirpass_leaderboard_rank", table_name="cirpass_leaderboard_entries")
    op.drop_table("cirpass_leaderboard_entries")

    op.drop_index("ix_cirpass_snapshot_fetched_at", table_name="cirpass_story_snapshots")
    op.drop_table("cirpass_story_snapshots")
