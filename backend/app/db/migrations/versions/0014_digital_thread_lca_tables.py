"""Create thread_events and lca_calculations tables

Revision ID: 0014_digital_thread_lca_tables
Revises: 0013_edc_tables
Create Date: 2026-02-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0014_digital_thread_lca_tables"
down_revision = "0013_edc_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create lifecyclephase enum
    lifecyclephase = sa.Enum(
        "design",
        "manufacture",
        "logistics",
        "deploy",
        "operate",
        "maintain",
        "end_of_life",
        name="lifecyclephase",
    )
    lifecyclephase.create(op.get_bind(), checkfirst=True)

    # Create thread_events table
    op.create_table(
        "thread_events",
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
            "phase",
            lifecyclephase,
            nullable=False,
            comment="Product lifecycle phase",
        ),
        sa.Column(
            "event_type",
            sa.String(100),
            nullable=False,
            comment="Event type: material_sourced, assembled, shipped, etc.",
        ),
        sa.Column(
            "source",
            sa.String(255),
            nullable=False,
            comment="System or organization that emitted the event",
        ),
        sa.Column(
            "source_event_id",
            sa.String(255),
            nullable=True,
            comment="External event correlation ID",
        ),
        sa.Column(
            "payload",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            comment="Event-specific data",
        ),
        sa.Column(
            "parent_event_id",
            sa.Uuid(),
            sa.ForeignKey("thread_events.id"),
            nullable=True,
            comment="Causal parent event for event chains",
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
    op.create_index(
        "ix_thread_events_tenant_dpp_phase",
        "thread_events",
        ["tenant_id", "dpp_id", "phase"],
    )
    op.create_index(
        "ix_thread_events_tenant_created",
        "thread_events",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_thread_events_dpp_id",
        "thread_events",
        ["dpp_id"],
    )
    op.create_index(
        "ix_thread_events_parent",
        "thread_events",
        ["parent_event_id"],
    )

    # Create lca_calculations table
    op.create_table(
        "lca_calculations",
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
            "revision_no",
            sa.Integer(),
            nullable=False,
            comment="DPP revision number used for the calculation",
        ),
        sa.Column(
            "methodology",
            sa.String(100),
            nullable=False,
            comment="Calculation methodology, e.g. activity-based-gwp",
        ),
        sa.Column(
            "scope",
            sa.String(50),
            nullable=False,
            comment="LCA scope: cradle-to-gate, gate-to-gate, cradle-to-grave",
        ),
        sa.Column(
            "total_gwp_kg_co2e",
            sa.Double(),
            nullable=False,
            comment="Total GWP in kg CO2 equivalent",
        ),
        sa.Column(
            "impact_categories",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            comment="Multi-category impact results",
        ),
        sa.Column(
            "material_inventory",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            comment="Extracted input data for reproducibility",
        ),
        sa.Column(
            "factor_database_version",
            sa.String(50),
            nullable=False,
            comment="Emission factor database version used",
        ),
        sa.Column(
            "report_json",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            comment="Full detailed report",
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
    op.create_index(
        "ix_lca_calculations_tenant_dpp",
        "lca_calculations",
        ["tenant_id", "dpp_id"],
    )
    op.create_index(
        "ix_lca_calculations_dpp_revision",
        "lca_calculations",
        ["dpp_id", "revision_no"],
    )


def downgrade() -> None:
    op.drop_index("ix_lca_calculations_dpp_revision", table_name="lca_calculations")
    op.drop_index("ix_lca_calculations_tenant_dpp", table_name="lca_calculations")
    op.drop_table("lca_calculations")

    op.drop_index("ix_thread_events_parent", table_name="thread_events")
    op.drop_index("ix_thread_events_dpp_id", table_name="thread_events")
    op.drop_index("ix_thread_events_tenant_created", table_name="thread_events")
    op.drop_index("ix_thread_events_tenant_dpp_phase", table_name="thread_events")
    op.drop_table("thread_events")

    sa.Enum(name="lifecyclephase").drop(op.get_bind(), checkfirst=True)
