"""Add dataspace publication jobs table

Revision ID: 0036_ds_publication_jobs
Revises: 0035_opcua_pipeline
Create Date: 2026-02-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0036_ds_publication_jobs"
down_revision = "0035_opcua_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ds_pub_status = sa.Enum(
        "queued",
        "running",
        "succeeded",
        "failed",
        name="dataspacepublicationstatus",
    )
    ds_pub_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "dataspace_publication_jobs",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuid_generate_v7()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "dpp_id",
            sa.Uuid(),
            sa.ForeignKey("dpps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued",
                "running",
                "succeeded",
                "failed",
                name="dataspacepublicationstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column(
            "target",
            sa.String(50),
            nullable=False,
            server_default="catena-x",
            comment="Target ecosystem, e.g. catena-x",
        ),
        sa.Column(
            "artifact_refs",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            comment="Published artifact references (DTR IDs, EDC asset IDs, etc.)",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_ds_pub_jobs_dpp", "dataspace_publication_jobs", ["dpp_id"])
    op.create_index("ix_ds_pub_jobs_status", "dataspace_publication_jobs", ["status"])

    # Enable Row Level Security
    op.execute("ALTER TABLE dataspace_publication_jobs ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY dataspace_publication_jobs_tenant_isolation
        ON dataspace_publication_jobs
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS dataspace_publication_jobs_tenant_isolation"
        " ON dataspace_publication_jobs"
    )
    op.execute("ALTER TABLE dataspace_publication_jobs DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_ds_pub_jobs_status", table_name="dataspace_publication_jobs")
    op.drop_index("ix_ds_pub_jobs_dpp", table_name="dataspace_publication_jobs")
    op.drop_table("dataspace_publication_jobs")

    sa.Enum(name="dataspacepublicationstatus").drop(op.get_bind(), checkfirst=True)
