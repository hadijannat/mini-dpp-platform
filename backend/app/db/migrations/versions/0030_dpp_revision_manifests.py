"""Add supplementary/doc-hints manifests to DPP revisions

Revision ID: 0030_dpp_revision_manifests
Revises: 0029_data_carriers
Create Date: 2026-02-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0030_dpp_revision_manifests"
down_revision = "0029_data_carriers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dpp_revisions",
        sa.Column(
            "supplementary_manifest",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Supplementary AASX files manifest mapped to tenant attachment records",
        ),
    )
    op.add_column(
        "dpp_revisions",
        sa.Column(
            "doc_hints_manifest",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Resolved deterministic documentation hints snapshot for this revision",
        ),
    )


def downgrade() -> None:
    op.drop_column("dpp_revisions", "doc_hints_manifest")
    op.drop_column("dpp_revisions", "supplementary_manifest")
