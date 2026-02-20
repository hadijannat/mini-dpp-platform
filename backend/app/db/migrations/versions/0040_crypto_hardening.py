"""Add crypto hardening metadata columns for digests, chains, and anchoring.

Revision ID: 0040_crypto_hardening
Revises: 0039_template_catalog_metadata
Create Date: 2026-02-20
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0040_crypto_hardening"
down_revision = "0039_template_catalog_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # dpp_revisions
    # ------------------------------------------------------------------
    op.add_column(
        "dpp_revisions",
        sa.Column(
            "digest_algorithm",
            sa.String(length=32),
            nullable=False,
            server_default="sha-256",
        ),
    )
    op.add_column(
        "dpp_revisions",
        sa.Column(
            "digest_canonicalization",
            sa.String(length=64),
            nullable=False,
            server_default="legacy-json-v1",
        ),
    )
    op.add_column("dpp_revisions", sa.Column("wrapped_dek", sa.Text(), nullable=True))
    op.add_column("dpp_revisions", sa.Column("kek_id", sa.String(length=255), nullable=True))
    op.add_column(
        "dpp_revisions",
        sa.Column("dek_wrapping_algorithm", sa.String(length=64), nullable=True),
    )
    op.execute(
        """
        UPDATE dpp_revisions
        SET digest_algorithm = COALESCE(NULLIF(digest_algorithm, ''), 'sha-256'),
            digest_canonicalization = COALESCE(
                NULLIF(digest_canonicalization, ''),
                'legacy-json-v1'
            )
        """
    )

    # ------------------------------------------------------------------
    # audit_events
    # ------------------------------------------------------------------
    op.add_column(
        "audit_events",
        sa.Column(
            "hash_algorithm",
            sa.String(length=32),
            nullable=False,
            server_default="sha-256",
        ),
    )
    op.add_column(
        "audit_events",
        sa.Column(
            "hash_canonicalization",
            sa.String(length=64),
            nullable=False,
            server_default="legacy-json-v1",
        ),
    )
    op.execute(
        """
        UPDATE audit_events
        SET hash_algorithm = COALESCE(NULLIF(hash_algorithm, ''), 'sha-256'),
            hash_canonicalization = COALESCE(
                NULLIF(hash_canonicalization, ''),
                'legacy-json-v1'
            )
        """
    )

    # ------------------------------------------------------------------
    # audit_merkle_roots
    # ------------------------------------------------------------------
    op.add_column(
        "audit_merkle_roots",
        sa.Column("signature_kid", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "audit_merkle_roots",
        sa.Column("signature_algorithm", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "audit_merkle_roots",
        sa.Column("timestamp_hash_algorithm", sa.String(length=32), nullable=True),
    )
    op.execute(
        """
        UPDATE audit_merkle_roots
        SET signature_algorithm = COALESCE(
                signature_algorithm,
                CASE WHEN signature IS NOT NULL THEN 'Ed25519' ELSE NULL END
            ),
            timestamp_hash_algorithm = COALESCE(
                timestamp_hash_algorithm,
                CASE WHEN tsa_token IS NOT NULL THEN 'sha-256' ELSE NULL END
            )
        """
    )


def downgrade() -> None:
    op.drop_column("audit_merkle_roots", "timestamp_hash_algorithm")
    op.drop_column("audit_merkle_roots", "signature_algorithm")
    op.drop_column("audit_merkle_roots", "signature_kid")

    op.drop_column("audit_events", "hash_canonicalization")
    op.drop_column("audit_events", "hash_algorithm")

    op.drop_column("dpp_revisions", "dek_wrapping_algorithm")
    op.drop_column("dpp_revisions", "kek_id")
    op.drop_column("dpp_revisions", "wrapped_dek")
    op.drop_column("dpp_revisions", "digest_canonicalization")
    op.drop_column("dpp_revisions", "digest_algorithm")
