"""Initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    op.execute(
        """
CREATE OR REPLACE FUNCTION uuid_generate_v7()
RETURNS uuid AS $$
DECLARE
    unix_ts_ms bytea;
    uuid_bytes bytea;
BEGIN
    unix_ts_ms = substring(int8send(floor(extract(epoch from clock_timestamp()) * 1000)::bigint) from 3);
    uuid_bytes = unix_ts_ms || gen_random_bytes(10);

    -- Set version 7
    uuid_bytes = set_byte(uuid_bytes, 6, (get_byte(uuid_bytes, 6) & 15) | 112);
    -- Set variant (RFC 4122)
    uuid_bytes = set_byte(uuid_bytes, 8, (get_byte(uuid_bytes, 8) & 63) | 128);

    RETURN encode(uuid_bytes, 'hex')::uuid;
END;
$$ LANGUAGE plpgsql VOLATILE;
        """
    )

    userrole_enum = sa.Enum("viewer", "publisher", "admin", name="userrole")
    dppstatus_enum = sa.Enum("draft", "published", "archived", name="dppstatus")
    revisionstate_enum = sa.Enum("draft", "published", name="revisionstate")
    policytype_enum = sa.Enum("route", "submodel", "element", name="policytype")
    policyeffect_enum = sa.Enum(
        "allow", "deny", "mask", "hide", "encrypt_required", name="policyeffect"
    )
    connectortype_enum = sa.Enum("catena_x", "rest", "file", name="connectortype")
    connectorstatus_enum = sa.Enum("active", "disabled", "error", name="connectorstatus")

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v7()"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("role", userrole_enum, nullable=False, server_default="viewer"),
        sa.Column(
            "attrs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("subject"),
    )
    op.create_index("ix_users_subject", "users", ["subject"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "dpps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v7()"),
            nullable=False,
        ),
        sa.Column("status", dppstatus_enum, nullable=False, server_default="draft"),
        sa.Column("owner_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "asset_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("qr_payload", sa.Text(), nullable=True),
        sa.Column("current_published_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_subject"], ["users.subject"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dpps_owner_subject", "dpps", ["owner_subject"], unique=False)
    op.create_index("ix_dpps_status", "dpps", ["status"], unique=False)
    op.create_index(
        "ix_dpps_asset_ids", "dpps", ["asset_ids"], unique=False, postgresql_using="gin"
    )

    op.create_table(
        "dpp_revisions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v7()"),
            nullable=False,
        ),
        sa.Column("dpp_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("state", revisionstate_enum, nullable=False, server_default="draft"),
        sa.Column("aas_env_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("digest_sha256", sa.String(length=64), nullable=False),
        sa.Column("signed_jws", sa.Text(), nullable=True),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["dpp_id"], ["dpps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dpp_id", "revision_no", name="uq_dpp_revision_no"),
    )
    op.create_index("ix_dpp_revisions_dpp_id", "dpp_revisions", ["dpp_id"], unique=False)
    op.create_index("ix_dpp_revisions_state", "dpp_revisions", ["state"], unique=False)

    op.create_foreign_key(
        "fk_dpps_current_published_revision",
        "dpps",
        "dpp_revisions",
        ["current_published_revision_id"],
        ["id"],
    )

    op.create_table(
        "encrypted_values",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v7()"),
            nullable=False,
        ),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("json_pointer_path", sa.Text(), nullable=False),
        sa.Column("cipher_text", sa.LargeBinary(), nullable=False),
        sa.Column("key_id", sa.String(length=255), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("algorithm", sa.String(length=50), nullable=False, server_default="AES-256-GCM"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["revision_id"], ["dpp_revisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_id", "json_pointer_path", name="uq_encrypted_value_path"),
    )
    op.create_index(
        "ix_encrypted_values_revision_id", "encrypted_values", ["revision_id"], unique=False
    )

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

    op.create_table(
        "policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v7()"),
            nullable=False,
        ),
        sa.Column("dpp_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("policy_type", policytype_enum, nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("effect", policyeffect_enum, nullable=False),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.ForeignKeyConstraint(["dpp_id"], ["dpps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policies_dpp_id", "policies", ["dpp_id"], unique=False)
    op.create_index("ix_policies_type_target", "policies", ["policy_type", "target"], unique=False)

    op.create_table(
        "connectors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v7()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("connector_type", connectortype_enum, nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", connectorstatus_enum, nullable=False, server_default="disabled"),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
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
    )
    op.create_index("ix_connectors_type", "connectors", ["connector_type"], unique=False)
    op.create_index("ix_connectors_status", "connectors", ["status"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v7()"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("decision", sa.String(length=50), nullable=True),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_subject", "audit_events", ["subject"], unique=False)
    op.create_index("ix_audit_events_action", "audit_events", ["action"], unique=False)
    op.create_index(
        "ix_audit_events_resource", "audit_events", ["resource_type", "resource_id"], unique=False
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_resource", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_subject", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_connectors_status", table_name="connectors")
    op.drop_index("ix_connectors_type", table_name="connectors")
    op.drop_table("connectors")

    op.drop_index("ix_policies_type_target", table_name="policies")
    op.drop_index("ix_policies_dpp_id", table_name="policies")
    op.drop_table("policies")

    op.drop_index("ix_templates_template_key", table_name="templates")
    op.drop_table("templates")

    op.drop_index("ix_encrypted_values_revision_id", table_name="encrypted_values")
    op.drop_table("encrypted_values")

    op.drop_constraint("fk_dpps_current_published_revision", "dpps", type_="foreignkey")

    op.drop_index("ix_dpp_revisions_state", table_name="dpp_revisions")
    op.drop_index("ix_dpp_revisions_dpp_id", table_name="dpp_revisions")
    op.drop_table("dpp_revisions")

    op.drop_index("ix_dpps_asset_ids", table_name="dpps")
    op.drop_index("ix_dpps_status", table_name="dpps")
    op.drop_index("ix_dpps_owner_subject", table_name="dpps")
    op.drop_table("dpps")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_subject", table_name="users")
    op.drop_table("users")

    for enum_name in [
        "connectorstatus",
        "connectortype",
        "policyeffect",
        "policytype",
        "revisionstate",
        "dppstatus",
        "userrole",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

    op.execute("DROP FUNCTION IF EXISTS uuid_generate_v7()")
