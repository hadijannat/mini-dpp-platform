"""Create webhook_subscriptions and webhook_delivery_log tables

Revision ID: 0018_webhooks
Revises: 0017_epcis_named_queries
Create Date: 2026-02-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0018_webhooks"
down_revision = "0017_epcis_named_queries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_subscriptions",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuid_generate_v7()"),
            primary_key=True,
        ),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("events", JSONB(), nullable=False),
        sa.Column("secret", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by_subject", sa.String(255), nullable=False),
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
    op.create_index("ix_webhook_subscriptions_tenant", "webhook_subscriptions", ["tenant_id"])
    op.create_index("ix_webhook_subscriptions_active", "webhook_subscriptions", ["active"])

    op.create_table(
        "webhook_delivery_log",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("uuid_generate_v7()"),
            primary_key=True,
        ),
        sa.Column(
            "subscription_id",
            sa.Uuid(),
            sa.ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("attempt", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("success", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_webhook_delivery_log_subscription", "webhook_delivery_log", ["subscription_id"]
    )
    op.create_index("ix_webhook_delivery_log_created", "webhook_delivery_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("webhook_delivery_log")
    op.drop_table("webhook_subscriptions")
