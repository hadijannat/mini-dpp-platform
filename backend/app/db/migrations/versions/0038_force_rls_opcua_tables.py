"""Force RLS on OPC UA and dataspace publication tables.

Revision ID: 0038_force_rls_opcua_tables
Revises: 0037epcissourceeventid
Create Date: 2026-02-19
"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "0038_force_rls_opcua_tables"
down_revision = "0037epcissourceeventid"
branch_labels = None
depends_on = None

_TABLES = (
    "opcua_sources",
    "opcua_nodesets",
    "opcua_mappings",
    "opcua_jobs",
    "opcua_deadletters",
    "opcua_inventory_snapshots",
    "dataspace_publication_jobs",
)


def _is_current_role_table_owner(table_name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        text(
            """
            SELECT pg_get_userbyid(c.relowner) = current_user
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            WHERE c.relname = :table_name
              AND c.relkind = 'r'
              AND n.nspname = current_schema()
            LIMIT 1
            """
        ),
        {"table_name": table_name},
    ).scalar_one_or_none()
    return result is True


def upgrade() -> None:
    for table_name in _TABLES:
        if not _is_current_role_table_owner(table_name):
            continue
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table_name in _TABLES:
        if not _is_current_role_table_owner(table_name):
            continue
        op.execute(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY")
