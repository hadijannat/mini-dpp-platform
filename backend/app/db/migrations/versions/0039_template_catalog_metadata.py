"""Add template catalog metadata fields for public SMT sandbox.

Revision ID: 0039_template_catalog_metadata
Revises: 0038_force_rls_opcua_tables
Create Date: 2026-02-20
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0039_template_catalog_metadata"
down_revision = "0038_force_rls_opcua_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "templates",
        sa.Column(
            "catalog_status",
            sa.String(length=32),
            nullable=False,
            server_default="published",
        ),
    )
    op.add_column(
        "templates",
        sa.Column(
            "display_name",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column("templates", sa.Column("catalog_folder", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE templates
        SET display_name = COALESCE(NULLIF(display_name, ''), initcap(replace(template_key, '-', ' ')))
        """
    )
    op.execute(
        """
        UPDATE templates
        SET display_name = template_key
        WHERE display_name = ''
        """
    )
    op.execute(
        """
        UPDATE templates
        SET catalog_folder = NULLIF(
            regexp_replace(source_file_path, '/[0-9]+/[0-9]+(/[0-9]+)?/[^/]+$', ''),
            ''
        )
        WHERE source_file_path IS NOT NULL
        """
    )

    op.create_index("ix_templates_catalog_status", "templates", ["catalog_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_templates_catalog_status", table_name="templates")
    op.drop_column("templates", "catalog_folder")
    op.drop_column("templates", "display_name")
    op.drop_column("templates", "catalog_status")
