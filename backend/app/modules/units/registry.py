"""UoM registry loading from database and packaged seed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.units.models import UomDataSpecification, UomRegistryEntry

logger = get_logger(__name__)

_DEFAULT_SEED_RELATIVE = Path("data/uom.seed.json")


class UomRegistryService:
    """Resolver for canonical UoM entries from DB + packaged seed."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    def load_seed_entries(self) -> list[UomRegistryEntry]:
        path = _resolve_seed_path()
        if path is None:
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("uom_seed_load_failed", path=str(path), error=str(exc))
            return []

        rows = payload.get("units") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return []

        entries: list[UomRegistryEntry] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            cd_id = str(row.get("cdId") or "").strip()
            if not cd_id:
                continue
            data_spec = UomDataSpecification.from_payload(
                {
                    "preferredName": row.get("preferredName", {}),
                    "symbol": row.get("symbol"),
                    "specificUnitID": row.get("specificUnitID"),
                    "definition": row.get("definition", {}),
                    "preferredNameQuantity": row.get("preferredNameQuantity", {}),
                    "quantityID": row.get("quantityID"),
                    "classificationSystem": row.get("classificationSystem"),
                    "classificationSystemVersion": row.get("classificationSystemVersion"),
                }
            )
            if data_spec is None:
                continue
            entries.append(
                UomRegistryEntry(
                    cd_id=cd_id,
                    data_specification=data_spec,
                    source="seed",
                )
            )

        entries.sort(key=lambda entry: entry.cd_id)
        return entries

    async def load_db_entries(self) -> list[UomRegistryEntry]:
        if self._session is None:
            return []

        from app.db.models import UomUnit

        result = await self._session.execute(
            select(UomUnit).where(UomUnit.active.is_(True)).order_by(UomUnit.cd_id.asc())
        )
        rows = list(result.scalars().all())

        entries: list[UomRegistryEntry] = []
        for row in rows:
            data_spec = UomDataSpecification(
                preferred_name=dict(row.preferred_name or {}),
                symbol=row.symbol,
                specific_unit_id=row.specific_unit_id,
                definition=dict(row.definition or {}),
                preferred_name_quantity=dict(row.preferred_name_quantity or {}),
                quantity_id=row.quantity_id,
                classification_system=row.classification_system,
                classification_system_version=row.classification_system_version,
            )
            entries.append(
                UomRegistryEntry(
                    cd_id=row.cd_id,
                    data_specification=data_spec,
                    source=row.source,
                )
            )
        return entries

    async def load_effective_entries(self) -> list[UomRegistryEntry]:
        """Return DB entries first, then append seed-only fallbacks."""
        seed_entries = self.load_seed_entries()
        db_entries = await self.load_db_entries()

        by_cd_id: dict[str, UomRegistryEntry] = {}
        for entry in seed_entries:
            by_cd_id[entry.cd_id] = entry
        for entry in db_entries:
            by_cd_id[entry.cd_id] = entry

        return [by_cd_id[key] for key in sorted(by_cd_id.keys())]


def build_registry_indexes(
    entries: list[UomRegistryEntry],
) -> tuple[
    dict[str, UomRegistryEntry],
    dict[str, list[UomRegistryEntry]],
    dict[str, list[UomRegistryEntry]],
]:
    by_cd_id: dict[str, UomRegistryEntry] = {}
    by_specific_unit_id: dict[str, list[UomRegistryEntry]] = {}
    by_symbol: dict[str, list[UomRegistryEntry]] = {}

    for entry in entries:
        by_cd_id[entry.cd_id] = entry

        specific = entry.data_specification.specific_unit_id.strip()
        if specific:
            by_specific_unit_id.setdefault(specific, []).append(entry)

        symbol = entry.data_specification.symbol.strip()
        if symbol:
            by_symbol.setdefault(symbol, []).append(entry)

    for key in list(by_specific_unit_id.keys()):
        by_specific_unit_id[key].sort(key=lambda item: item.cd_id)
    for key in list(by_symbol.keys()):
        by_symbol[key].sort(key=lambda item: item.cd_id)

    return by_cd_id, by_specific_unit_id, by_symbol


def registry_entries_to_payload(entries: list[UomRegistryEntry]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for entry in sorted(entries, key=lambda item: item.cd_id):
        payload.append(
            {
                "cdId": entry.cd_id,
                "source": entry.source,
                **entry.data_specification.to_payload(),
            }
        )
    return payload


def _resolve_seed_path() -> Path | None:
    settings = get_settings()
    override = settings.uom_registry_seed_path
    if override:
        candidate = Path(override).expanduser().resolve()
        if candidate.exists():
            return candidate
        logger.warning("uom_seed_override_missing", path=str(candidate))

    packaged = (Path(__file__).resolve().parent / _DEFAULT_SEED_RELATIVE).resolve()
    if packaged.exists():
        return packaged

    return None
