"""Add UoM registry table and raw template payload storage.

Revision ID: 0046_uom_registry_raw_template
Revises: 0045_rfid_tenant_domains
Create Date: 2026-02-22
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert

# revision identifiers, used by Alembic.
revision = "0046_uom_registry_raw_template"
down_revision = "0045_rfid_tenant_domains"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "templates",
        sa.Column("template_json_raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute(
        """
        UPDATE templates
        SET template_json_raw = template_json
        WHERE template_json_raw IS NULL
        """
    )

    op.create_table(
        "uom_units",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("cd_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column(
            "preferred_name",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "definition",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("specific_unit_id", sa.Text(), nullable=False),
        sa.Column(
            "classification_system",
            sa.Text(),
            nullable=False,
            server_default="UNECE Rec 20",
        ),
        sa.Column("classification_system_version", sa.Text(), nullable=True),
        sa.Column(
            "preferred_name_quantity",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("quantity_id", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="seed"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cd_id", name="uq_uom_units_cd_id"),
    )
    op.create_index("ix_uom_units_cd_id", "uom_units", ["cd_id"], unique=False)
    op.create_index(
        "ix_uom_units_specific_unit_id",
        "uom_units",
        ["specific_unit_id"],
        unique=False,
    )
    op.create_index("ix_uom_units_symbol", "uom_units", ["symbol"], unique=False)

    _seed_registry_rows()


def downgrade() -> None:
    op.drop_index("ix_uom_units_symbol", table_name="uom_units")
    op.drop_index("ix_uom_units_specific_unit_id", table_name="uom_units")
    op.drop_index("ix_uom_units_cd_id", table_name="uom_units")
    op.drop_table("uom_units")
    op.drop_column("templates", "template_json_raw")


def _seed_registry_rows() -> None:
    connection = op.get_bind()

    rows = _load_seed_rows()
    if not rows:
        rows = _fallback_seed_rows()

    table = sa.table(
        "uom_units",
        sa.column("cd_id", sa.Text()),
        sa.column("symbol", sa.Text()),
        sa.column("preferred_name", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("definition", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("specific_unit_id", sa.Text()),
        sa.column("classification_system", sa.Text()),
        sa.column("classification_system_version", sa.Text()),
        sa.column("preferred_name_quantity", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("quantity_id", sa.Text()),
        sa.column("source", sa.Text()),
        sa.column("active", sa.Boolean()),
    )

    payload: list[dict[str, Any]] = []
    for row in rows:
        payload.append(
            {
                "cd_id": row["cd_id"],
                "symbol": row["symbol"],
                "preferred_name": row.get("preferred_name", {}),
                "definition": row.get("definition", {}),
                "specific_unit_id": row["specific_unit_id"],
                "classification_system": row.get("classification_system", "UNECE Rec 20"),
                "classification_system_version": row.get("classification_system_version"),
                "preferred_name_quantity": row.get("preferred_name_quantity", {}),
                "quantity_id": row.get("quantity_id"),
                "source": row.get("source", "seed"),
                "active": bool(row.get("active", True)),
            }
        )

    if not payload:
        return

    stmt = insert(table).values(payload)
    stmt = stmt.on_conflict_do_nothing(index_elements=["cd_id"])
    connection.execute(stmt)


def _load_seed_rows() -> list[dict[str, Any]]:
    try:
        seed_path = (
            Path(__file__).resolve().parents[4] / "modules" / "units" / "data" / "uom.seed.json"
        )
        if not seed_path.exists():
            warnings.warn(
                "UoM seed file unavailable during migration; using fallback baseline rows.",
                RuntimeWarning,
                stacklevel=2,
            )
            return []
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
        rows = payload.get("units") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return []

        normalized: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            cd_id = str(row.get("cdId") or "").strip()
            symbol = str(row.get("symbol") or "").strip()
            specific_unit_id = str(row.get("specificUnitID") or "").strip()
            if not cd_id or not symbol or not specific_unit_id:
                continue
            normalized.append(
                {
                    "cd_id": cd_id,
                    "symbol": symbol,
                    "preferred_name": row.get("preferredName", {}),
                    "definition": row.get("definition", {}),
                    "specific_unit_id": specific_unit_id,
                    "classification_system": row.get("classificationSystem", "UNECE Rec 20"),
                    "classification_system_version": row.get("classificationSystemVersion"),
                    "preferred_name_quantity": row.get("preferredNameQuantity", {}),
                    "quantity_id": row.get("quantityID"),
                    "source": "seed",
                    "active": True,
                }
            )

        return normalized
    except Exception:
        warnings.warn(
            "Failed to load UoM seed file during migration; using fallback baseline rows.",
            RuntimeWarning,
            stacklevel=2,
        )
        return []


def _fallback_seed_rows() -> list[dict[str, Any]]:
    return [
        {
            "cd_id": "urn:unece:rec20:MTR",
            "symbol": "m",
            "preferred_name": {"en": "metre"},
            "definition": {"en": "SI base unit of length."},
            "specific_unit_id": "MTR",
            "classification_system": "UNECE Rec 20",
            "classification_system_version": "2024",
            "preferred_name_quantity": {"en": "length"},
            "quantity_id": "LEN",
            "source": "fallback",
            "active": True,
        }
    ]
