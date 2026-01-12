"""Add DPP master templates

Revision ID: 0008_dpp_masters
Revises: 0007_admin_bypass_privileges
Create Date: 2026-01-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0008_dpp_masters"
down_revision = "0007_admin_bypass_privileges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'masterversionstatus') THEN
                CREATE TYPE masterversionstatus AS ENUM ('released', 'deprecated');
            END IF;
        END
        $$;
        """
    )

    op.create_table(
        "dpp_masters",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v7()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "selected_templates",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("draft_template_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "draft_variables",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column("updated_by_subject", sa.String(length=255), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "product_id", name="uq_dpp_masters_tenant_product"),
    )
    op.create_index("ix_dpp_masters_product_id", "dpp_masters", ["product_id"], unique=False)
    op.create_index("ix_dpp_masters_tenant_id", "dpp_masters", ["tenant_id"], unique=False)

    op.create_table(
        "dpp_master_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v7()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("master_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "released",
                "deprecated",
                name="masterversionstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="released",
        ),
        sa.Column(
            "aliases",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("template_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "variables",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("released_by_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "released_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deprecation_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["master_id"], ["dpp_masters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("master_id", "version", name="uq_dpp_master_version"),
    )
    op.create_index(
        "ix_dpp_master_versions_master",
        "dpp_master_versions",
        ["master_id"],
        unique=False,
    )
    op.create_index(
        "ix_dpp_master_versions_tenant_id",
        "dpp_master_versions",
        ["tenant_id"],
        unique=False,
    )

    for table_name in ("dpp_masters", "dpp_master_versions"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table_name}_tenant_isolation
            ON {table_name}
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            """
        )


def downgrade() -> None:
    for table_name in ("dpp_master_versions", "dpp_masters"):
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name}")
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_dpp_master_versions_tenant_id", table_name="dpp_master_versions")
    op.drop_index("ix_dpp_master_versions_master", table_name="dpp_master_versions")
    op.drop_table("dpp_master_versions")

    op.drop_index("ix_dpp_masters_tenant_id", table_name="dpp_masters")
    op.drop_index("ix_dpp_masters_product_id", table_name="dpp_masters")
    op.drop_table("dpp_masters")

    op.execute("DROP TYPE IF EXISTS masterversionstatus")
