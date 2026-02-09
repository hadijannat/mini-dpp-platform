"""Add template_provenance column to dpp_revisions

Revision ID: 0023_dpp_revision_template_provenance
Revises: 0022_complete_tenant_rls
Create Date: 2026-02-09
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0023_dpp_revision_template_provenance"
down_revision = "0022_complete_tenant_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dpp_revisions",
        sa.Column("template_provenance", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dpp_revisions", "template_provenance")
