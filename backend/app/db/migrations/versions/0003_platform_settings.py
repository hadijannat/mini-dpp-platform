"""Add platform settings

Revision ID: 0003_platform_settings
Revises: 0002_templates_table
Create Date: 2026-01-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0003_platform_settings"
down_revision = "0002_templates_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v7()"),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_platform_settings_key"),
    )
    op.create_index(
        "ix_platform_settings_key",
        "platform_settings",
        ["key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_platform_settings_key", table_name="platform_settings")
    op.drop_table("platform_settings")
