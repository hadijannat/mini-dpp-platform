"""Add master alias table and semver constraint

Revision ID: 0009_master_aliases_semver
Revises: 0008_dpp_masters
Create Date: 2026-01-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0009_master_aliases_semver"
down_revision = "0008_dpp_masters"
branch_labels = None
depends_on = None

SEMVER_CHECK_NAME = "ck_dpp_master_versions_semver"
SEMVER_REGEX = r"^[0-9]+\\.[0-9]+\\.[0-9]+([+-][0-9A-Za-z.-]+)?$"


def upgrade() -> None:
    op.create_table(
        "dpp_master_aliases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v7()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("master_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alias", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["master_id"], ["dpp_masters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["dpp_master_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("master_id", "alias", name="uq_dpp_master_alias"),
    )
    op.create_index(
        "ix_dpp_master_aliases_master",
        "dpp_master_aliases",
        ["master_id"],
        unique=False,
    )
    op.create_index(
        "ix_dpp_master_aliases_alias",
        "dpp_master_aliases",
        ["alias"],
        unique=False,
    )
    op.create_index(
        "ix_dpp_master_aliases_tenant_id",
        "dpp_master_aliases",
        ["tenant_id"],
        unique=False,
    )

    op.create_check_constraint(
        SEMVER_CHECK_NAME,
        "dpp_master_versions",
        f"version ~ '{SEMVER_REGEX}'",
    )

    op.execute(
        """
        INSERT INTO dpp_master_aliases (id, tenant_id, master_id, version_id, alias, created_at)
        SELECT
            uuid_generate_v7(),
            v.tenant_id,
            v.master_id,
            v.id,
            alias_entry.value,
            now()
        FROM dpp_master_versions v
        CROSS JOIN LATERAL jsonb_array_elements_text(v.aliases) AS alias_entry(value)
        ON CONFLICT (master_id, alias) DO NOTHING;
        """
    )

    op.execute("ALTER TABLE dpp_master_aliases ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY dpp_master_aliases_tenant_isolation
        ON dpp_master_aliases
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS dpp_master_aliases_tenant_isolation ON dpp_master_aliases")
    op.execute("ALTER TABLE dpp_master_aliases DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_dpp_master_aliases_tenant_id", table_name="dpp_master_aliases")
    op.drop_index("ix_dpp_master_aliases_alias", table_name="dpp_master_aliases")
    op.drop_index("ix_dpp_master_aliases_master", table_name="dpp_master_aliases")
    op.drop_table("dpp_master_aliases")

    op.drop_constraint(SEMVER_CHECK_NAME, "dpp_master_versions", type_="check")
