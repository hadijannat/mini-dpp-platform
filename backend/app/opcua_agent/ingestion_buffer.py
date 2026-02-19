"""In-memory coalescing buffer for OPC UA → DPP value updates.

Collects incoming values keyed by (tenant_id, dpp_id, target_submodel_id,
target_aas_path).  Latest value wins — duplicate keys are overwritten so
that the flush engine commits only the most recent reading per path.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class BufferEntry:
    """Single buffered value destined for a DPP submodel field."""

    tenant_id: UUID
    dpp_id: UUID
    mapping_id: UUID
    target_submodel_id: str
    target_aas_path: str
    value: Any
    timestamp: datetime


# Key type: (tenant_id, dpp_id, target_submodel_id, target_aas_path)
_BufferKey = tuple[UUID, UUID, str, str]


class IngestionBuffer:
    """Thread-safe, async-safe coalescing buffer.

    Callers :meth:`put` values; the flush engine calls :meth:`drain` to
    atomically retrieve and clear all buffered entries.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._entries: dict[_BufferKey, BufferEntry] = {}

    async def put(
        self,
        *,
        tenant_id: UUID,
        dpp_id: UUID,
        mapping_id: UUID,
        target_submodel_id: str,
        target_aas_path: str,
        value: Any,
        timestamp: datetime,
    ) -> None:
        """Insert or overwrite a value — latest write wins."""
        key: _BufferKey = (tenant_id, dpp_id, target_submodel_id, target_aas_path)
        entry = BufferEntry(
            tenant_id=tenant_id,
            dpp_id=dpp_id,
            mapping_id=mapping_id,
            target_submodel_id=target_submodel_id,
            target_aas_path=target_aas_path,
            value=value,
            timestamp=timestamp,
        )
        async with self._lock:
            self._entries[key] = entry

    async def put_entry(self, entry: BufferEntry) -> None:
        """Insert a pre-built buffer entry."""
        key: _BufferKey = (
            entry.tenant_id,
            entry.dpp_id,
            entry.target_submodel_id,
            entry.target_aas_path,
        )
        async with self._lock:
            self._entries[key] = entry

    async def put_entries(self, entries: list[BufferEntry]) -> None:
        """Insert multiple entries atomically."""
        if not entries:
            return
        async with self._lock:
            for entry in entries:
                key: _BufferKey = (
                    entry.tenant_id,
                    entry.dpp_id,
                    entry.target_submodel_id,
                    entry.target_aas_path,
                )
                self._entries[key] = entry

    async def drain(self) -> list[BufferEntry]:
        """Atomically drain all entries and return them as a list."""
        async with self._lock:
            entries = list(self._entries.values())
            self._entries.clear()
        return entries

    def size(self) -> int:
        """Approximate entry count (no lock — read is atomic for dicts)."""
        return len(self._entries)
