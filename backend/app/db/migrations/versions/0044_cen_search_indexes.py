"""Add CEN-oriented search indexes for identifier lookups and cursor search.

Revision ID: 0044_cen_search_indexes
Revises: 0043_cen_carrier_qa_and_binding
Create Date: 2026-02-21
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0044_cen_search_indexes"
down_revision = "0043_cen_carrier_qa_and_binding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_external_identifiers_tenant_entity_status",
        "external_identifiers",
        ["tenant_id", "entity_type", "status"],
    )
    op.create_index(
        "ix_dpp_identifiers_tenant_external",
        "dpp_identifiers",
        ["tenant_id", "external_identifier_id"],
    )
    op.create_index(
        "ix_dpp_identifiers_tenant_dpp",
        "dpp_identifiers",
        ["tenant_id", "dpp_id"],
    )
    op.create_index(
        "ix_dpps_tenant_status_id",
        "dpps",
        ["tenant_id", "status", "id"],
    )
    op.create_index(
        "ix_dpps_asset_ids_global_asset_id",
        "dpps",
        [sa.text("(asset_ids->>'globalAssetId')")],
    )


def downgrade() -> None:
    op.drop_index("ix_dpps_asset_ids_global_asset_id", table_name="dpps")
    op.drop_index("ix_dpps_tenant_status_id", table_name="dpps")
    op.drop_index("ix_dpp_identifiers_tenant_dpp", table_name="dpp_identifiers")
    op.drop_index("ix_dpp_identifiers_tenant_external", table_name="dpp_identifiers")
    op.drop_index(
        "ix_external_identifiers_tenant_entity_status",
        table_name="external_identifiers",
    )
