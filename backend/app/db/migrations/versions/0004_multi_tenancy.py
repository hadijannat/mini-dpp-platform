"""Multi-tenant data model

Revision ID: 0004_multi_tenancy
Revises: 0003_platform_settings
Create Date: 2026-01-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0004_multi_tenancy"
down_revision = "0003_platform_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tenantstatus') THEN
                CREATE TYPE tenantstatus AS ENUM ('active', 'disabled');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tenantrole') THEN
                CREATE TYPE tenantrole AS ENUM ('viewer', 'publisher', 'tenant_admin');
            END IF;
        END
        $$;
        """
    )

    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v7()"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active",
                "disabled",
                name="tenantstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
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
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=False)
    op.create_index("ix_tenants_status", "tenants", ["status"], unique=False)

    op.create_table(
        "tenant_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v7()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "viewer",
                "publisher",
                "tenant_admin",
                name="tenantrole",
                create_type=False,
            ),
            nullable=False,
            server_default="viewer",
        ),
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
        sa.UniqueConstraint("tenant_id", "user_subject", name="uq_tenant_membership"),
    )
    op.create_index("ix_tenant_members_tenant_id", "tenant_members", ["tenant_id"], unique=False)
    op.create_index(
        "ix_tenant_members_user_subject", "tenant_members", ["user_subject"], unique=False
    )

    conn = op.get_bind()
    default_tenant_id = conn.execute(
        sa.text(
            """
            INSERT INTO tenants (slug, name, status)
            VALUES (:slug, :name, :status)
            RETURNING id
            """
        ),
        {
            "slug": "default",
            "name": "Default Tenant",
            "status": "active",
        },
    ).scalar_one()

    # Add tenant_id columns (nullable for backfill)
    for table_name in (
        "dpps",
        "dpp_revisions",
        "encrypted_values",
        "policies",
        "connectors",
        "audit_events",
    ):
        op.add_column(
            table_name,
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        )

    # Backfill tenant_id
    conn.execute(
        sa.text("UPDATE dpps SET tenant_id = :tenant_id"), {"tenant_id": default_tenant_id}
    )
    conn.execute(
        sa.text(
            """
            UPDATE dpp_revisions r
            SET tenant_id = d.tenant_id
            FROM dpps d
            WHERE r.dpp_id = d.id
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE encrypted_values ev
            SET tenant_id = r.tenant_id
            FROM dpp_revisions r
            WHERE ev.revision_id = r.id
            """
        )
    )
    conn.execute(
        sa.text("UPDATE policies SET tenant_id = :tenant_id"), {"tenant_id": default_tenant_id}
    )
    conn.execute(
        sa.text("UPDATE connectors SET tenant_id = :tenant_id"), {"tenant_id": default_tenant_id}
    )
    conn.execute(
        sa.text("UPDATE audit_events SET tenant_id = :tenant_id"), {"tenant_id": default_tenant_id}
    )

    # Backfill memberships for existing users
    conn.execute(
        sa.text(
            """
            INSERT INTO tenant_members (tenant_id, user_subject, role)
            SELECT :tenant_id, subject,
                CASE WHEN role = 'admin' THEN 'tenant_admin' ELSE role::text END::tenantrole
            FROM users
            """
        ),
        {"tenant_id": default_tenant_id},
    )

    # Set tenant_id NOT NULL and add FKs/indexes
    for table_name in (
        "dpps",
        "dpp_revisions",
        "encrypted_values",
        "policies",
        "connectors",
        "audit_events",
    ):
        op.alter_column(table_name, "tenant_id", nullable=False)
        op.create_index(
            f"ix_{table_name}_tenant_id",
            table_name,
            ["tenant_id"],
            unique=False,
        )
        op.create_foreign_key(
            f"fk_{table_name}_tenant_id",
            table_name,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    for table_name in (
        "audit_events",
        "connectors",
        "policies",
        "encrypted_values",
        "dpp_revisions",
        "dpps",
    ):
        op.drop_constraint(f"fk_{table_name}_tenant_id", table_name, type_="foreignkey")
        op.drop_index(f"ix_{table_name}_tenant_id", table_name=table_name)
        op.drop_column(table_name, "tenant_id")

    op.drop_index("ix_tenant_members_user_subject", table_name="tenant_members")
    op.drop_index("ix_tenant_members_tenant_id", table_name="tenant_members")
    op.drop_table("tenant_members")

    op.drop_index("ix_tenants_status", table_name="tenants")
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")

    sa.Enum(name="tenantrole").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="tenantstatus").drop(op.get_bind(), checkfirst=True)
