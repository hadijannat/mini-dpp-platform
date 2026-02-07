"""Create epcis_events table for EPCIS 2.0 supply-chain event traceability

Revision ID: 0016_epcis_events
Revises: 0015_template_source_metadata
Create Date: 2026-02-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0016_epcis_events"
down_revision = "0015_template_source_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create epciseventtype enum
    epciseventtype = sa.Enum(
        "ObjectEvent",
        "AggregationEvent",
        "TransactionEvent",
        "TransformationEvent",
        "AssociationEvent",
        name="epciseventtype",
    )
    epciseventtype.create(op.get_bind(), checkfirst=True)

    # Create epcis_events table
    op.create_table(
        "epcis_events",
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
            "event_id",
            sa.String(512),
            nullable=False,
            comment="Unique EPCIS event URI (urn:uuid:...)",
        ),
        sa.Column(
            "event_type",
            postgresql.ENUM(
                "ObjectEvent",
                "AggregationEvent",
                "TransactionEvent",
                "TransformationEvent",
                "AssociationEvent",
                name="epciseventtype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "event_time",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the event occurred",
        ),
        sa.Column(
            "event_time_zone_offset",
            sa.String(10),
            nullable=False,
            comment="Timezone offset, e.g. +01:00",
        ),
        sa.Column(
            "action",
            sa.String(20),
            nullable=True,
            comment="ADD, OBSERVE, or DELETE (NULL for TransformationEvent)",
        ),
        sa.Column(
            "biz_step",
            sa.String(100),
            nullable=True,
            comment="CBV business step short name",
        ),
        sa.Column(
            "disposition",
            sa.String(100),
            nullable=True,
            comment="CBV disposition short name",
        ),
        sa.Column(
            "read_point",
            sa.String(512),
            nullable=True,
            comment="Where the event was observed (URI)",
        ),
        sa.Column(
            "biz_location",
            sa.String(512),
            nullable=True,
            comment="Business location where objects reside after event (URI)",
        ),
        sa.Column(
            "payload",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            comment="Type-specific data: epcList, parentID, childEPCs, sensor data, etc.",
        ),
        sa.Column(
            "error_declaration",
            JSONB(),
            nullable=True,
            comment="EPCIS error declaration for event corrections",
        ),
        sa.Column(
            "created_by_subject",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Create indexes
    op.create_index(
        "ix_epcis_events_tenant_dpp_time",
        "epcis_events",
        ["tenant_id", "dpp_id", "event_time"],
    )
    op.create_index(
        "ix_epcis_events_event_id",
        "epcis_events",
        ["event_id"],
        unique=True,
    )
    op.create_index(
        "ix_epcis_events_biz_step",
        "epcis_events",
        ["biz_step"],
    )
    op.create_index(
        "ix_epcis_events_payload",
        "epcis_events",
        ["payload"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_epcis_events_payload", table_name="epcis_events")
    op.drop_index("ix_epcis_events_biz_step", table_name="epcis_events")
    op.drop_index("ix_epcis_events_event_id", table_name="epcis_events")
    op.drop_index("ix_epcis_events_tenant_dpp_time", table_name="epcis_events")
    op.drop_table("epcis_events")

    sa.Enum(name="epciseventtype").drop(op.get_bind(), checkfirst=True)
