"""Add ownership visibility, resource shares, and batch import job persistence

Revision ID: 0025_ownership_visibility_access
Revises: 0024_role_upgrade_requests
Create Date: 2026-02-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0025_ownership_visibility_access"
down_revision = "0024_role_upgrade_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sa.Enum("owner_team", "tenant", name="visibilityscope").create(op.get_bind(), checkfirst=True)

    op.add_column(
        "dpps",
        sa.Column(
            "visibility_scope",
            postgresql.ENUM(
                "owner_team",
                "tenant",
                name="visibilityscope",
                create_type=False,
            ),
            nullable=False,
            server_default="owner_team",
        ),
    )
    op.add_column(
        "connectors",
        sa.Column(
            "visibility_scope",
            postgresql.ENUM(
                "owner_team",
                "tenant",
                name="visibilityscope",
                create_type=False,
            ),
            nullable=False,
            server_default="owner_team",
        ),
    )

    op.create_table(
        "resource_shares",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("user_subject", sa.String(length=255), nullable=False),
        sa.Column("permission", sa.String(length=32), nullable=False, server_default="read"),
        sa.Column("granted_by_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "resource_type",
            "resource_id",
            "user_subject",
            name="uq_resource_shares_target_user",
        ),
    )
    op.create_index(
        "ix_resource_shares_lookup",
        "resource_shares",
        ["tenant_id", "resource_type", "resource_id"],
    )
    op.create_index(
        "ix_resource_shares_user",
        "resource_shares",
        ["tenant_id", "user_subject"],
    )

    op.create_table(
        "batch_import_jobs",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("requested_by_subject", sa.String(length=255), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_batch_import_jobs_tenant_created",
        "batch_import_jobs",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_batch_import_jobs_requested_by",
        "batch_import_jobs",
        ["requested_by_subject"],
    )

    op.create_table(
        "batch_import_job_items",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "job_id",
            sa.UUID(),
            sa.ForeignKey("batch_import_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_index", sa.Integer(), nullable=False),
        sa.Column(
            "dpp_id", sa.UUID(), sa.ForeignKey("dpps.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "item_index", name="uq_batch_import_job_item_index"),
    )
    op.create_index("ix_batch_import_job_items_job", "batch_import_job_items", ["job_id"])
    op.create_index(
        "ix_batch_import_job_items_tenant_job",
        "batch_import_job_items",
        ["tenant_id", "job_id"],
    )

    for table_name in ("resource_shares", "batch_import_jobs", "batch_import_job_items"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table_name}_tenant_isolation
            ON {table_name}
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            """
        )


def downgrade() -> None:
    for table_name in ("batch_import_job_items", "batch_import_jobs", "resource_shares"):
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name}")
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_batch_import_job_items_tenant_job", table_name="batch_import_job_items")
    op.drop_index("ix_batch_import_job_items_job", table_name="batch_import_job_items")
    op.drop_table("batch_import_job_items")

    op.drop_index("ix_batch_import_jobs_requested_by", table_name="batch_import_jobs")
    op.drop_index("ix_batch_import_jobs_tenant_created", table_name="batch_import_jobs")
    op.drop_table("batch_import_jobs")

    op.drop_index("ix_resource_shares_user", table_name="resource_shares")
    op.drop_index("ix_resource_shares_lookup", table_name="resource_shares")
    op.drop_table("resource_shares")

    op.drop_column("connectors", "visibility_scope")
    op.drop_column("dpps", "visibility_scope")

    sa.Enum("owner_team", "tenant", name="visibilityscope").drop(op.get_bind(), checkfirst=True)
