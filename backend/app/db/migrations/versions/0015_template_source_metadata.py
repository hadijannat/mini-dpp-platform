"""Add deterministic template source metadata columns

Revision ID: 0015_template_source_metadata
Revises: 0014_digital_thread_lca_tables
Create Date: 2026-02-07
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0015_template_source_metadata"
down_revision = "0014_digital_thread_lca_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("templates", sa.Column("resolved_version", sa.String(length=20), nullable=True))
    op.add_column("templates", sa.Column("source_repo_ref", sa.String(length=255), nullable=True))
    op.add_column("templates", sa.Column("source_file_path", sa.Text(), nullable=True))
    op.add_column("templates", sa.Column("source_file_sha", sa.String(length=128), nullable=True))
    op.add_column("templates", sa.Column("source_kind", sa.String(length=16), nullable=True))
    op.add_column("templates", sa.Column("selection_strategy", sa.String(length=32), nullable=True))

    op.execute(
        "UPDATE templates SET resolved_version = idta_version WHERE resolved_version IS NULL"
    )


def downgrade() -> None:
    op.drop_column("templates", "selection_strategy")
    op.drop_column("templates", "source_kind")
    op.drop_column("templates", "source_file_sha")
    op.drop_column("templates", "source_file_path")
    op.drop_column("templates", "source_repo_ref")
    op.drop_column("templates", "resolved_version")
