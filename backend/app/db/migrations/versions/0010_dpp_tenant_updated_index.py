"""Add composite index on dpps(tenant_id, updated_at) for paginated listing

Revision ID: 0010_dpp_tenant_updated_index
Revises: 0009_master_aliases_semver
Create Date: 2026-02-06
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0010_dpp_tenant_updated_index"
down_revision = "0009_master_aliases_semver"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_dpps_tenant_updated",
        "dpps",
        ["tenant_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_dpps_tenant_updated", table_name="dpps")
