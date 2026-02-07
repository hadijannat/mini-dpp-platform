"""Add crypto hash chain columns to audit_events and create audit_merkle_roots

Revision ID: 0011_audit_crypto_columns
Revises: 0010_dpp_tenant_updated_index
Create Date: 2026-02-07
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0011_audit_crypto_columns"
down_revision = "0010_dpp_tenant_updated_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add crypto columns to audit_events
    op.add_column(
        "audit_events",
        sa.Column(
            "event_hash",
            sa.String(64),
            nullable=True,
            comment="SHA-256 hash",
        ),
    )
    op.add_column(
        "audit_events",
        sa.Column(
            "prev_event_hash",
            sa.String(64),
            nullable=True,
            comment="Previous event hash",
        ),
    )
    op.add_column(
        "audit_events",
        sa.Column(
            "chain_sequence",
            sa.Integer(),
            nullable=True,
            comment="Monotonic sequence per tenant",
        ),
    )
    op.create_index(
        "ix_audit_events_tenant_chain",
        "audit_events",
        ["tenant_id", "chain_sequence"],
    )

    # Create audit_merkle_roots table
    op.create_table(
        "audit_merkle_roots",
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
            "root_hash",
            sa.String(64),
            nullable=False,
            comment="SHA-256 Merkle root hash",
        ),
        sa.Column(
            "event_count",
            sa.Integer(),
            nullable=False,
            comment="Number of events in this Merkle batch",
        ),
        sa.Column(
            "first_sequence",
            sa.Integer(),
            nullable=False,
            comment="First chain_sequence in batch",
        ),
        sa.Column(
            "last_sequence",
            sa.Integer(),
            nullable=False,
            comment="Last chain_sequence in batch",
        ),
        sa.Column(
            "signature",
            sa.Text(),
            nullable=True,
            comment="Ed25519 signature of root_hash",
        ),
        sa.Column(
            "tsa_token",
            sa.LargeBinary(),
            nullable=True,
            comment="RFC 3161 timestamp authority token",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_audit_merkle_roots_tenant",
        "audit_merkle_roots",
        ["tenant_id"],
    )
    op.create_index(
        "ix_audit_merkle_roots_sequences",
        "audit_merkle_roots",
        ["tenant_id", "first_sequence", "last_sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_merkle_roots_sequences", table_name="audit_merkle_roots")
    op.drop_index("ix_audit_merkle_roots_tenant", table_name="audit_merkle_roots")
    op.drop_table("audit_merkle_roots")

    op.drop_index("ix_audit_events_tenant_chain", table_name="audit_events")
    op.drop_column("audit_events", "chain_sequence")
    op.drop_column("audit_events", "prev_event_hash")
    op.drop_column("audit_events", "event_hash")
