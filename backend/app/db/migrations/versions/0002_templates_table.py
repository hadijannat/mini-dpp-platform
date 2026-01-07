"""Ensure templates table exists.

Revision ID: 0002_templates_table
Revises: 0001_initial
Create Date: 2026-01-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002_templates_table"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("templates"):
        op.create_table(
            "templates",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("uuid_generate_v7()"),
                nullable=False,
            ),
            sa.Column("template_key", sa.String(length=100), nullable=False),
            sa.Column("idta_version", sa.String(length=20), nullable=False),
            sa.Column("semantic_id", sa.Text(), nullable=False),
            sa.Column("source_url", sa.Text(), nullable=False),
            sa.Column("template_aasx", sa.LargeBinary(), nullable=True),
            sa.Column("template_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column(
                "fetched_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("template_key", "idta_version", name="uq_template_key_version"),
        )
        op.create_index("ix_templates_template_key", "templates", ["template_key"], unique=False)
        return

    indexes = {index["name"] for index in inspector.get_indexes("templates")}
    if "ix_templates_template_key" not in indexes:
        op.create_index("ix_templates_template_key", "templates", ["template_key"], unique=False)


def downgrade() -> None:
    # No-op: this migration repairs missing tables in existing DBs; dropping could destroy data.
    pass
