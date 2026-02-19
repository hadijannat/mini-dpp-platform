# OPC UA Phases 7-11 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the OPC UA agent worker, GTIN/GS1 identity binding, dataspace publication, EPCIS event triggers, and observability/secrets hardening to the mini-dpp-platform.

**Architecture:** Monolith-first agent at `backend/app/opcua_agent/` sharing the backend Docker image with a different entrypoint (`python -m app.opcua_agent`). The agent runs an asyncio event loop that polls for enabled mappings, subscribes to OPC UA data changes via asyncua, coalesces values in an in-memory buffer, and batch-flushes DPP revisions using advisory locks and the canonical patch engine. Phases 8-11 add GTIN support, dataspace publication, EPCIS triggers, and health/metrics.

**Tech Stack:** Python 3.12, asyncua (OPC UA), aiohttp (health server), prometheus_client (metrics), SQLAlchemy 2.0 async, FastAPI, PostgreSQL advisory locks

---

## Pre-requisite: Add New Dependencies

### Task 0: Add asyncua, aiohttp, prometheus_client to pyproject.toml

**Files:**
- Modify: `backend/pyproject.toml:78-81`

**Step 1: Add dependencies**

In `backend/pyproject.toml`, add three new packages after the `"structlog>=24.1.0",` line inside the `dependencies` array:

```toml
    # OPC UA Client
    "asyncua>=1.1.0",

    # Lightweight HTTP server (OPC UA agent health)
    "aiohttp>=3.9.0",

    # Prometheus metrics exposition
    "prometheus-client>=0.20.0",
```

**Step 2: Install dependencies**

Run: `cd backend && uv sync`
Expected: Dependencies resolve and install without conflicts.

**Step 3: Verify imports**

Run: `cd backend && uv run python -c "import asyncua; import aiohttp; import prometheus_client; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "feat(opcua): add asyncua, aiohttp, prometheus_client dependencies"
```

---

## Phase 7: OPC UA Agent Worker

### Task 1: Agent package `__init__.py` + `__main__.py`

**Files:**
- Create: `backend/app/opcua_agent/__init__.py`
- Create: `backend/app/opcua_agent/__main__.py`
- Test: `backend/tests/test_opcua_agent_main.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_opcua_agent_main.py
"""Tests for opcua_agent entry point — verifies graceful shutdown."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_agent_exits_when_opcua_disabled():
    """Agent should exit immediately if opcua_enabled=False."""
    with patch("app.opcua_agent.main.get_settings") as mock_settings:
        mock_settings.return_value.opcua_enabled = False
        mock_settings.return_value.database_url = "postgresql+asyncpg://x@localhost/x"
        mock_settings.return_value.database_pool_size = 5
        mock_settings.return_value.database_max_overflow = 10
        mock_settings.return_value.database_pool_timeout = 30
        mock_settings.return_value.debug = False

        from app.opcua_agent.main import run_agent

        # Should return without error
        await run_agent(max_cycles=1)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_opcua_agent_main.py::test_agent_exits_when_opcua_disabled -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.opcua_agent'`

**Step 3: Write minimal implementation**

```python
# backend/app/opcua_agent/__init__.py
"""OPC UA agent worker — runs as a separate process."""
```

```python
# backend/app/opcua_agent/__main__.py
"""Entry point: python -m app.opcua_agent"""

import asyncio
import sys

from app.opcua_agent.main import run_agent


def main() -> None:
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
```

```python
# backend/app/opcua_agent/main.py
"""Agent lifecycle — poll for mappings, subscribe, flush."""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

logger = logging.getLogger("opcua_agent")

# Graceful shutdown flag
_shutdown = asyncio.Event()


def _handle_signal(sig: signal.Signals) -> None:
    logger.info("Received %s — shutting down", sig.name)
    _shutdown.set()


async def run_agent(*, max_cycles: int = 0) -> None:
    """Main agent loop.

    Args:
        max_cycles: If > 0, exit after this many poll cycles (for testing).
    """
    settings = get_settings()
    if not settings.opcua_enabled:
        logger.info("OPC UA is disabled (opcua_enabled=false). Agent exiting.")
        return

    # Set up DB engine (agent-private, not shared with FastAPI)
    engine: AsyncEngine = create_async_engine(
        str(settings.database_url),
        pool_size=5,
        max_overflow=2,
        pool_pre_ping=True,
        echo=settings.debug,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal, sig)

    logger.info("OPC UA agent started. Poll interval=%ds", settings.opcua_agent_poll_interval_seconds)

    cycle = 0
    try:
        while not _shutdown.is_set():
            cycle += 1

            # Phase 1: Poll for enabled mappings and sync subscriptions
            # (implemented in Task 3-5)

            # Phase 2: Flush buffer to DPP revisions
            # (implemented in Task 6)

            if max_cycles > 0 and cycle >= max_cycles:
                break

            try:
                await asyncio.wait_for(
                    _shutdown.wait(),
                    timeout=settings.opcua_agent_poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass  # Normal — poll interval elapsed
    finally:
        await engine.dispose()
        logger.info("OPC UA agent stopped after %d cycles", cycle)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_opcua_agent_main.py::test_agent_exits_when_opcua_disabled -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/opcua_agent/__init__.py backend/app/opcua_agent/__main__.py backend/app/opcua_agent/main.py backend/tests/test_opcua_agent_main.py
git commit -m "feat(opcua): add agent entry point with feature-flag gate"
```

---

### Task 2: Ingestion buffer

**Files:**
- Create: `backend/app/opcua_agent/ingestion_buffer.py`
- Test: `backend/tests/test_opcua_ingestion_buffer.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_opcua_ingestion_buffer.py
"""Tests for the in-memory coalescing buffer."""

import uuid
from datetime import UTC, datetime

import pytest

from app.opcua_agent.ingestion_buffer import BufferEntry, IngestionBuffer


@pytest.mark.asyncio
async def test_buffer_put_and_drain():
    """put() stores latest value, drain() returns and clears all entries."""
    buf = IngestionBuffer()
    tid = uuid.uuid4()
    dpp_id = uuid.uuid4()
    mapping_id = uuid.uuid4()

    await buf.put(
        tenant_id=tid,
        dpp_id=dpp_id,
        mapping_id=mapping_id,
        target_submodel_id="sm-1",
        target_aas_path="Temperature",
        value=23.5,
        timestamp=datetime.now(tz=UTC),
    )
    await buf.put(
        tenant_id=tid,
        dpp_id=dpp_id,
        mapping_id=mapping_id,
        target_submodel_id="sm-1",
        target_aas_path="Temperature",
        value=24.1,  # newer value overwrites
        timestamp=datetime.now(tz=UTC),
    )

    entries = await buf.drain()
    assert len(entries) == 1
    assert entries[0].value == 24.1

    # After drain, buffer is empty
    assert await buf.drain() == []


@pytest.mark.asyncio
async def test_buffer_size():
    """size() reflects current buffer depth."""
    buf = IngestionBuffer()
    assert buf.size() == 0

    await buf.put(
        tenant_id=uuid.uuid4(),
        dpp_id=uuid.uuid4(),
        mapping_id=uuid.uuid4(),
        target_submodel_id="sm-1",
        target_aas_path="Pressure",
        value=101.3,
        timestamp=datetime.now(tz=UTC),
    )
    assert buf.size() == 1


@pytest.mark.asyncio
async def test_buffer_multiple_keys():
    """Different (dpp_id, target_path) combos are separate entries."""
    buf = IngestionBuffer()
    tid = uuid.uuid4()
    dpp1 = uuid.uuid4()
    dpp2 = uuid.uuid4()

    await buf.put(
        tenant_id=tid,
        dpp_id=dpp1,
        mapping_id=uuid.uuid4(),
        target_submodel_id="sm-1",
        target_aas_path="Temperature",
        value=20.0,
        timestamp=datetime.now(tz=UTC),
    )
    await buf.put(
        tenant_id=tid,
        dpp_id=dpp2,
        mapping_id=uuid.uuid4(),
        target_submodel_id="sm-2",
        target_aas_path="Humidity",
        value=55.0,
        timestamp=datetime.now(tz=UTC),
    )

    entries = await buf.drain()
    assert len(entries) == 2
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_opcua_ingestion_buffer.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# backend/app/opcua_agent/ingestion_buffer.py
"""In-memory coalescing buffer for OPC UA data changes.

Key design: latest-value-wins. If a node fires 100 data changes in 10s,
only the most recent value is flushed to the DPP. This prevents revision
explosion while ensuring DPPs always reflect the latest state.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class BufferEntry:
    """Single buffered value pending flush."""

    tenant_id: UUID
    dpp_id: UUID
    mapping_id: UUID
    target_submodel_id: str
    target_aas_path: str
    value: Any
    timestamp: datetime


# Buffer key: (tenant_id, dpp_id, target_submodel_id, target_aas_path)
_BufferKey = tuple[UUID, UUID, str, str]


class IngestionBuffer:
    """Thread-safe in-memory coalescing buffer.

    Keyed by (tenant_id, dpp_id, target_submodel_id, target_aas_path).
    Latest value for each key wins — intermediate values are discarded.
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
        """Insert or overwrite a value in the buffer."""
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

    async def drain(self) -> list[BufferEntry]:
        """Atomically drain all entries and return them."""
        async with self._lock:
            entries = list(self._entries.values())
            self._entries.clear()
            return entries

    def size(self) -> int:
        """Current number of buffered entries (no lock — approximate)."""
        return len(self._entries)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_opcua_ingestion_buffer.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/app/opcua_agent/ingestion_buffer.py backend/tests/test_opcua_ingestion_buffer.py
git commit -m "feat(opcua): add in-memory coalescing ingestion buffer"
```

---

### Task 3: Dead letter recorder

**Files:**
- Create: `backend/app/opcua_agent/deadletter.py`
- Test: `backend/tests/test_opcua_deadletter.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_opcua_deadletter.py
"""Tests for the dead letter recorder."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.opcua_agent.deadletter import record_dead_letter


@pytest.mark.asyncio
async def test_record_dead_letter_creates_row():
    """record_dead_letter should INSERT or UPDATE a dead letter row."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # No existing row
    mock_session.execute.return_value = mock_result

    await record_dead_letter(
        session=mock_session,
        tenant_id=uuid.uuid4(),
        mapping_id=uuid.uuid4(),
        value_payload={"raw": 42},
        error="TransformError: cast:number failed",
    )

    # Should have called execute (SELECT + INSERT) and flush
    assert mock_session.execute.call_count >= 1
    assert mock_session.flush.called
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_opcua_deadletter.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# backend/app/opcua_agent/deadletter.py
"""Dead letter queue for failed OPC UA → DPP mapping operations.

Records persistent failures so operators can diagnose broken mappings.
Increments count on repeated failures for the same mapping.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OPCUADeadLetter

logger = logging.getLogger("opcua_agent.deadletter")


async def record_dead_letter(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    mapping_id: UUID,
    value_payload: dict[str, Any],
    error: str,
) -> None:
    """Record or update a dead letter entry for a failed mapping.

    If an entry already exists for this mapping_id, increment count
    and update last_seen_at + error. Otherwise, create a new row.
    """
    q = select(OPCUADeadLetter).where(
        OPCUADeadLetter.tenant_id == tenant_id,
        OPCUADeadLetter.mapping_id == mapping_id,
    )
    result = await session.execute(q)
    existing = result.scalar_one_or_none()

    now = datetime.now(tz=UTC)
    if existing:
        existing.count += 1
        existing.last_seen_at = now
        existing.error = error
        existing.value_payload = value_payload
    else:
        dl = OPCUADeadLetter(
            tenant_id=tenant_id,
            mapping_id=mapping_id,
            value_payload=value_payload,
            error=error,
            count=1,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(dl)

    await session.flush()
    logger.warning(
        "Dead letter recorded for mapping %s: %s",
        mapping_id,
        error[:200],
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_opcua_deadletter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/opcua_agent/deadletter.py backend/tests/test_opcua_deadletter.py
git commit -m "feat(opcua): add dead letter recorder for failed mappings"
```

---

### Task 4: Flush engine

**Files:**
- Create: `backend/app/opcua_agent/flush_engine.py`
- Test: `backend/tests/test_opcua_flush_engine.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_opcua_flush_engine.py
"""Tests for the batch flush engine."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.opcua_agent.ingestion_buffer import BufferEntry


@pytest.mark.asyncio
async def test_group_entries_by_dpp():
    """_group_entries_by_dpp groups buffer entries by (tenant_id, dpp_id)."""
    from app.opcua_agent.flush_engine import _group_entries_by_dpp

    tid = uuid.uuid4()
    dpp1 = uuid.uuid4()
    dpp2 = uuid.uuid4()

    entries = [
        BufferEntry(
            tenant_id=tid,
            dpp_id=dpp1,
            mapping_id=uuid.uuid4(),
            target_submodel_id="sm-1",
            target_aas_path="Temp",
            value=22.0,
            timestamp=datetime.now(tz=UTC),
        ),
        BufferEntry(
            tenant_id=tid,
            dpp_id=dpp1,
            mapping_id=uuid.uuid4(),
            target_submodel_id="sm-1",
            target_aas_path="Humidity",
            value=55.0,
            timestamp=datetime.now(tz=UTC),
        ),
        BufferEntry(
            tenant_id=tid,
            dpp_id=dpp2,
            mapping_id=uuid.uuid4(),
            target_submodel_id="sm-2",
            target_aas_path="Pressure",
            value=1013.0,
            timestamp=datetime.now(tz=UTC),
        ),
    ]

    grouped = _group_entries_by_dpp(entries)
    assert len(grouped) == 2
    assert len(grouped[(tid, dpp1)]) == 2
    assert len(grouped[(tid, dpp2)]) == 1


@pytest.mark.asyncio
async def test_build_patch_operations():
    """_build_patch_operations creates set_value ops from entries."""
    from app.opcua_agent.flush_engine import _build_patch_operations

    tid = uuid.uuid4()
    dpp_id = uuid.uuid4()
    entry = BufferEntry(
        tenant_id=tid,
        dpp_id=dpp_id,
        mapping_id=uuid.uuid4(),
        target_submodel_id="sm-1",
        target_aas_path="Temperature.Value",
        value=22.5,
        timestamp=datetime.now(tz=UTC),
    )

    ops = _build_patch_operations([entry])
    assert len(ops) == 1
    assert ops[0]["submodel_id"] == "sm-1"
    assert ops[0]["operations"][0]["op"] == "set_value"
    assert ops[0]["operations"][0]["path"] == "Temperature.Value"
    assert ops[0]["operations"][0]["value"] == 22.5
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_opcua_flush_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# backend/app/opcua_agent/flush_engine.py
"""Batch flush engine — coalesced buffer → DPP revisions.

Drains the ingestion buffer, groups entries by DPP, acquires advisory
locks, and applies canonical patches to create new DPP revisions.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import DPP, DPPRevision
from app.modules.dpps.canonical_patch import apply_canonical_patch
from app.opcua_agent.deadletter import record_dead_letter
from app.opcua_agent.ingestion_buffer import BufferEntry, IngestionBuffer

logger = logging.getLogger("opcua_agent.flush")


def _group_entries_by_dpp(
    entries: list[BufferEntry],
) -> dict[tuple[UUID, UUID], list[BufferEntry]]:
    """Group buffer entries by (tenant_id, dpp_id)."""
    grouped: dict[tuple[UUID, UUID], list[BufferEntry]] = defaultdict(list)
    for entry in entries:
        grouped[(entry.tenant_id, entry.dpp_id)].append(entry)
    return dict(grouped)


def _build_patch_operations(
    entries: list[BufferEntry],
) -> list[dict[str, Any]]:
    """Build submodel-grouped patch operations from buffer entries.

    Returns a list of dicts, each with:
      - submodel_id: str
      - operations: list[dict] — canonical patch ops
    """
    by_submodel: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        by_submodel[entry.target_submodel_id].append({
            "op": "set_value",
            "path": entry.target_aas_path,
            "value": entry.value,
        })
    return [
        {"submodel_id": sm_id, "operations": ops}
        for sm_id, ops in by_submodel.items()
    ]


async def flush_buffer(
    buffer: IngestionBuffer,
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Drain the buffer and flush all coalesced values to DPP revisions.

    Returns the number of DPPs successfully updated.
    """
    entries = await buffer.drain()
    if not entries:
        return 0

    grouped = _group_entries_by_dpp(entries)
    flushed = 0

    for (tenant_id, dpp_id), group_entries in grouped.items():
        try:
            async with session_factory() as session:
                async with session.begin():
                    success = await _flush_single_dpp(
                        session=session,
                        tenant_id=tenant_id,
                        dpp_id=dpp_id,
                        entries=group_entries,
                    )
                    if success:
                        flushed += 1
        except Exception:
            logger.exception("Flush failed for DPP %s", dpp_id)
            # Record dead letters for all entries in this group
            try:
                async with session_factory() as dl_session:
                    async with dl_session.begin():
                        for entry in group_entries:
                            await record_dead_letter(
                                session=dl_session,
                                tenant_id=tenant_id,
                                mapping_id=entry.mapping_id,
                                value_payload={"value": str(entry.value)},
                                error="Flush failed — see agent logs",
                            )
            except Exception:
                logger.exception("Failed to record dead letters for DPP %s", dpp_id)

    return flushed


async def _flush_single_dpp(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    dpp_id: UUID,
    entries: list[BufferEntry],
) -> bool:
    """Flush coalesced entries to a single DPP. Returns True on success."""
    # Try advisory lock — non-blocking to avoid deadlocks
    lock_key = f"opcua:flush:{dpp_id}"
    lock_result = await session.execute(
        text("SELECT pg_try_advisory_xact_lock(hashtext(:key))"),
        {"key": lock_key},
    )
    acquired = lock_result.scalar()
    if not acquired:
        logger.info("Advisory lock busy for DPP %s — will retry next cycle", dpp_id)
        return False

    # Load DPP + latest revision
    dpp = await session.get(DPP, dpp_id)
    if not dpp or str(dpp.tenant_id) != str(tenant_id):
        logger.warning("DPP %s not found or tenant mismatch", dpp_id)
        return False

    latest_rev_q = (
        select(DPPRevision)
        .where(DPPRevision.dpp_id == dpp_id)
        .order_by(DPPRevision.version.desc())
        .limit(1)
    )
    latest_rev = (await session.execute(latest_rev_q)).scalar_one_or_none()
    if not latest_rev or not latest_rev.aas_env_json:
        logger.warning("DPP %s has no revision to patch", dpp_id)
        return False

    # Build and apply patches per submodel
    patch_groups = _build_patch_operations(entries)
    aas_env = latest_rev.aas_env_json
    total_applied = 0

    for group in patch_groups:
        try:
            result = apply_canonical_patch(
                aas_env_json=aas_env,
                submodel_id=group["submodel_id"],
                operations=group["operations"],
                contract=None,  # OPC UA agent bypasses contract validation
                strict=False,
            )
            aas_env = result.aas_env_json
            total_applied += result.applied_operations
        except Exception as exc:
            logger.warning(
                "Patch failed for DPP %s submodel %s: %s",
                dpp_id,
                group["submodel_id"],
                exc,
            )
            # Record dead letters for affected entries
            for entry in entries:
                if entry.target_submodel_id == group["submodel_id"]:
                    await record_dead_letter(
                        session=session,
                        tenant_id=tenant_id,
                        mapping_id=entry.mapping_id,
                        value_payload={"value": str(entry.value)},
                        error=str(exc)[:500],
                    )

    if total_applied == 0:
        return False

    # Create new revision
    new_version = (latest_rev.version or 0) + 1
    new_rev = DPPRevision(
        dpp_id=dpp_id,
        version=new_version,
        aas_env_json=aas_env,
        created_by="system:opcua-agent",
        change_summary=f"OPC UA batch flush: {total_applied} operations",
    )
    session.add(new_rev)
    await session.flush()

    logger.info(
        "Flushed DPP %s: v%d → v%d (%d ops)",
        dpp_id,
        new_version - 1,
        new_version,
        total_applied,
    )
    return True
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_opcua_flush_engine.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/app/opcua_agent/flush_engine.py backend/tests/test_opcua_flush_engine.py
git commit -m "feat(opcua): add batch flush engine with advisory locks"
```

---

### Task 5: Connection manager

**Files:**
- Create: `backend/app/opcua_agent/connection_manager.py`
- Test: `backend/tests/test_opcua_connection_manager.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_opcua_connection_manager.py
"""Tests for OPC UA connection manager."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.opcua_agent.connection_manager import ConnectionManager


@pytest.mark.asyncio
async def test_connection_manager_connect_and_disconnect():
    """ConnectionManager should create and close asyncua clients."""
    manager = ConnectionManager(max_per_tenant=3)

    source_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    with patch("app.opcua_agent.connection_manager.Client") as MockClient:
        mock_client = AsyncMock()
        mock_client.get_namespace_array = AsyncMock(return_value=["urn:test"])
        MockClient.return_value = mock_client

        client = await manager.connect(
            source_id=source_id,
            tenant_id=tenant_id,
            endpoint_url="opc.tcp://test-server:4840",
        )

        assert client is mock_client
        mock_client.connect.assert_awaited_once()
        assert manager.connection_count(tenant_id) == 1

        await manager.disconnect(source_id)
        mock_client.disconnect.assert_awaited_once()
        assert manager.connection_count(tenant_id) == 0


@pytest.mark.asyncio
async def test_connection_manager_enforces_tenant_limit():
    """Should raise when tenant exceeds max_per_tenant connections."""
    manager = ConnectionManager(max_per_tenant=1)
    tenant_id = uuid.uuid4()

    with patch("app.opcua_agent.connection_manager.Client") as MockClient:
        mock_client = AsyncMock()
        mock_client.get_namespace_array = AsyncMock(return_value=["urn:test"])
        MockClient.return_value = mock_client

        await manager.connect(
            source_id=uuid.uuid4(),
            tenant_id=tenant_id,
            endpoint_url="opc.tcp://test-server:4840",
        )

        with pytest.raises(ValueError, match="limit"):
            await manager.connect(
                source_id=uuid.uuid4(),
                tenant_id=tenant_id,
                endpoint_url="opc.tcp://test-server:4841",
            )
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_opcua_connection_manager.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# backend/app/opcua_agent/connection_manager.py
"""OPC UA connection lifecycle manager.

Maintains a per-source asyncua Client pool with tenant-level limits
and exponential backoff on connection failures.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

from asyncua import Client

logger = logging.getLogger("opcua_agent.connections")


@dataclass
class _ConnectionEntry:
    source_id: UUID
    tenant_id: UUID
    endpoint_url: str
    client: Client
    backoff_seconds: float = 1.0


class ConnectionManager:
    """Manages OPC UA client connections per source.

    Enforces a per-tenant connection limit to prevent resource exhaustion.
    """

    MAX_BACKOFF = 120.0  # seconds

    def __init__(self, *, max_per_tenant: int = 5) -> None:
        self._max_per_tenant = max_per_tenant
        self._connections: dict[UUID, _ConnectionEntry] = {}  # source_id → entry

    def connection_count(self, tenant_id: UUID) -> int:
        """Active connections for a given tenant."""
        return sum(
            1 for e in self._connections.values() if e.tenant_id == tenant_id
        )

    async def connect(
        self,
        *,
        source_id: UUID,
        tenant_id: UUID,
        endpoint_url: str,
        security_policy: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> Client:
        """Create and connect an asyncua Client for a source.

        Raises ValueError if tenant has reached connection limit.
        """
        if source_id in self._connections:
            return self._connections[source_id].client

        if self.connection_count(tenant_id) >= self._max_per_tenant:
            raise ValueError(
                f"Tenant {tenant_id} has reached the connection limit "
                f"of {self._max_per_tenant}"
            )

        client = Client(url=endpoint_url, timeout=10)

        if username and password:
            client.set_user(username)
            client.set_password(password)

        await client.connect()
        logger.info("Connected to %s (source %s)", endpoint_url, source_id)

        self._connections[source_id] = _ConnectionEntry(
            source_id=source_id,
            tenant_id=tenant_id,
            endpoint_url=endpoint_url,
            client=client,
        )
        return client

    async def disconnect(self, source_id: UUID) -> None:
        """Disconnect and remove a source's client."""
        entry = self._connections.pop(source_id, None)
        if entry:
            try:
                await entry.client.disconnect()
                logger.info("Disconnected source %s", source_id)
            except Exception:
                logger.exception("Error disconnecting source %s", source_id)

    async def disconnect_all(self) -> None:
        """Disconnect all active clients."""
        source_ids = list(self._connections.keys())
        for source_id in source_ids:
            await self.disconnect(source_id)

    def get_client(self, source_id: UUID) -> Client | None:
        """Return the asyncua Client for a source, or None."""
        entry = self._connections.get(source_id)
        return entry.client if entry else None
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_opcua_connection_manager.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/app/opcua_agent/connection_manager.py backend/tests/test_opcua_connection_manager.py
git commit -m "feat(opcua): add connection manager with tenant limits"
```

---

### Task 6: Subscription handler

**Files:**
- Create: `backend/app/opcua_agent/subscription_handler.py`
- Test: `backend/tests/test_opcua_subscription_handler.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_opcua_subscription_handler.py
"""Tests for the OPC UA subscription handler."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.opcua_agent.ingestion_buffer import IngestionBuffer
from app.opcua_agent.subscription_handler import DataChangeHandler


@pytest.mark.asyncio
async def test_data_change_handler_puts_to_buffer():
    """DataChangeHandler should write values to the ingestion buffer."""
    buffer = IngestionBuffer()
    handler = DataChangeHandler(
        buffer=buffer,
        tenant_id=uuid.uuid4(),
        dpp_id=uuid.uuid4(),
        mapping_id=uuid.uuid4(),
        target_submodel_id="sm-1",
        target_aas_path="Temperature",
        transform_expr=None,
    )

    # Simulate OPC UA data change notification
    mock_node = MagicMock()
    mock_node.nodeid = MagicMock()
    mock_node.nodeid.to_string.return_value = "ns=2;s=Temperature"
    val = 23.5
    data = MagicMock()
    data.monitored_item = MagicMock()
    data.monitored_item.Value = MagicMock()
    data.monitored_item.Value.Value = MagicMock()
    data.monitored_item.Value.Value.Value = val

    await handler.datachange_notification(mock_node, val, data)

    entries = await buffer.drain()
    assert len(entries) == 1
    assert entries[0].value == 23.5
    assert entries[0].target_aas_path == "Temperature"


@pytest.mark.asyncio
async def test_data_change_handler_applies_transform():
    """Handler should apply transform expression before buffering."""
    buffer = IngestionBuffer()
    handler = DataChangeHandler(
        buffer=buffer,
        tenant_id=uuid.uuid4(),
        dpp_id=uuid.uuid4(),
        mapping_id=uuid.uuid4(),
        target_submodel_id="sm-1",
        target_aas_path="Temperature",
        transform_expr="scale:0.001|round:2",
    )

    mock_node = MagicMock()
    val = 12345
    data = MagicMock()

    await handler.datachange_notification(mock_node, val, data)

    entries = await buffer.drain()
    assert len(entries) == 1
    assert entries[0].value == 12.35
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_opcua_subscription_handler.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# backend/app/opcua_agent/subscription_handler.py
"""OPC UA subscription and data change handling.

Receives asyncua monitored item notifications and feeds transformed
values into the ingestion buffer.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.modules.opcua.transform import TransformError, apply_transform
from app.opcua_agent.ingestion_buffer import IngestionBuffer

logger = logging.getLogger("opcua_agent.subscription")


class DataChangeHandler:
    """Handler for OPC UA data change notifications.

    Each handler is bound to a single mapping and writes transformed
    values into the shared ingestion buffer.
    """

    def __init__(
        self,
        *,
        buffer: IngestionBuffer,
        tenant_id: UUID,
        dpp_id: UUID,
        mapping_id: UUID,
        target_submodel_id: str,
        target_aas_path: str,
        transform_expr: str | None,
    ) -> None:
        self._buffer = buffer
        self._tenant_id = tenant_id
        self._dpp_id = dpp_id
        self._mapping_id = mapping_id
        self._target_submodel_id = target_submodel_id
        self._target_aas_path = target_aas_path
        self._transform_expr = transform_expr

    async def datachange_notification(
        self, node: Any, val: Any, data: Any
    ) -> None:
        """Called by asyncua when a monitored item value changes."""
        try:
            transformed = val
            if self._transform_expr:
                transformed = apply_transform(self._transform_expr, val)

            await self._buffer.put(
                tenant_id=self._tenant_id,
                dpp_id=self._dpp_id,
                mapping_id=self._mapping_id,
                target_submodel_id=self._target_submodel_id,
                target_aas_path=self._target_aas_path,
                value=transformed,
                timestamp=datetime.now(tz=UTC),
            )
        except TransformError:
            logger.warning(
                "Transform failed for mapping %s (expr=%s, value=%r)",
                self._mapping_id,
                self._transform_expr,
                val,
                exc_info=True,
            )
        except Exception:
            logger.exception(
                "Unexpected error in data change handler for mapping %s",
                self._mapping_id,
            )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_opcua_subscription_handler.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/app/opcua_agent/subscription_handler.py backend/tests/test_opcua_subscription_handler.py
git commit -m "feat(opcua): add subscription handler with transform DSL"
```

---

### Task 7: Wire agent main loop + Docker Compose

**Files:**
- Modify: `backend/app/opcua_agent/main.py` (update poll + flush phases)
- Modify: `docker-compose.yml` (add opcua-agent service)
- Test: `backend/tests/test_opcua_agent_main.py` (add integration test)

**Step 1: Update `main.py` with full poll + flush wiring**

Replace the placeholder comments in `backend/app/opcua_agent/main.py`'s `run_agent()` with:

```python
# In run_agent(), replace the two placeholder comments with:

    from app.opcua_agent.connection_manager import ConnectionManager
    from app.opcua_agent.flush_engine import flush_buffer
    from app.opcua_agent.ingestion_buffer import IngestionBuffer

    buffer = IngestionBuffer()
    conn_manager = ConnectionManager(
        max_per_tenant=settings.opcua_max_connections_per_tenant,
    )

    logger.info(
        "OPC UA agent started. Poll interval=%ds, flush interval=%ds",
        settings.opcua_agent_poll_interval_seconds,
        settings.opcua_batch_commit_interval_seconds,
    )

    cycle = 0
    try:
        while not _shutdown.is_set():
            cycle += 1

            # Phase 1: Poll for enabled mappings and sync subscriptions
            try:
                await _sync_subscriptions(session_factory, conn_manager, buffer)
            except Exception:
                logger.exception("Error syncing subscriptions")

            # Phase 2: Flush buffer to DPP revisions
            try:
                flushed = await flush_buffer(buffer, session_factory)
                if flushed > 0:
                    logger.info("Flushed %d DPP(s)", flushed)
            except Exception:
                logger.exception("Error flushing buffer")

            if max_cycles > 0 and cycle >= max_cycles:
                break

            try:
                await asyncio.wait_for(
                    _shutdown.wait(),
                    timeout=settings.opcua_agent_poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass
    finally:
        await conn_manager.disconnect_all()
        await engine.dispose()
        logger.info("OPC UA agent stopped after %d cycles", cycle)
```

Add `_sync_subscriptions` stub at the bottom of `main.py`:

```python
async def _sync_subscriptions(
    session_factory: async_sessionmaker[AsyncSession],
    conn_manager: ConnectionManager,
    buffer: IngestionBuffer,
) -> None:
    """Poll DB for enabled mappings and sync OPC UA subscriptions.

    Full implementation connects to OPC UA servers and creates monitored
    items. For now, this is a no-op placeholder that will be wired to
    the connection_manager and subscription_handler in production use.
    """
    # TODO: Phase 7 full implementation — query enabled mappings,
    # connect/disconnect sources, create/remove subscriptions
    pass
```

**Step 2: Add opcua-agent to `docker-compose.yml`**

Before the `networks:` block at the bottom, add:

```yaml
  # =============================================================================
  # OPC UA Agent - Background Worker
  # =============================================================================
  opcua-agent:
    build:
      context: .
      dockerfile: backend/Dockerfile
      target: development
    container_name: dpp-opcua-agent
    command: >
      sh -c "python -m app.opcua_agent"
    environment:
      - ENVIRONMENT=development
      - DATABASE_URL=postgresql+asyncpg://dpp_user:dpp_dev_password_2024@postgres:5432/dpp_platform
      - REDIS_URL=redis://redis:6379/0
      - ENCRYPTION_MASTER_KEY=${ENCRYPTION_MASTER_KEY:-dGVzdC1rZXktMzItYnl0ZXMtbG9uZy4uLg==}
      - OPCUA_ENABLED=${OPCUA_ENABLED:-false}
    volumes:
      - ./backend:/app:cached
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - dpp-network
```

**Step 3: Run existing tests to verify no regressions**

Run: `cd backend && uv run pytest tests/test_opcua_agent_main.py tests/test_opcua_ingestion_buffer.py tests/test_opcua_flush_engine.py tests/test_opcua_connection_manager.py tests/test_opcua_subscription_handler.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/app/opcua_agent/main.py docker-compose.yml
git commit -m "feat(opcua): wire agent main loop and add Docker Compose service"
```

---

## Phase 8: GTIN + GS1 Digital Link Identity Binding

### Task 8: Add gtin to AssetIdsInput

**Files:**
- Modify: `backend/app/modules/dpps/router.py:144-151`
- Test: `backend/tests/test_opcua_gtin.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_opcua_gtin.py
"""Tests for GTIN field on AssetIdsInput."""

import pytest
from pydantic import ValidationError


def test_asset_ids_accepts_valid_gtin():
    """AssetIdsInput should accept a valid GTIN-13."""
    from app.modules.dpps.router import AssetIdsInput

    ids = AssetIdsInput(gtin="4006381333931")
    assert ids.gtin == "4006381333931"


def test_asset_ids_accepts_none_gtin():
    """AssetIdsInput should accept None gtin (optional)."""
    from app.modules.dpps.router import AssetIdsInput

    ids = AssetIdsInput()
    assert ids.gtin is None


def test_asset_ids_rejects_invalid_gtin():
    """AssetIdsInput should reject GTIN with bad check digit."""
    from app.modules.dpps.router import AssetIdsInput

    with pytest.raises(ValidationError, match="GTIN"):
        AssetIdsInput(gtin="1234567890123")  # Bad check digit
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_opcua_gtin.py -v`
Expected: FAIL — `AssetIdsInput` has no `gtin` field

**Step 3: Add gtin field to AssetIdsInput**

In `backend/app/modules/dpps/router.py`, add to `AssetIdsInput` class after `globalAssetId`:

```python
class AssetIdsInput(BaseModel):
    """Input model for asset identifiers."""

    manufacturerPartId: str | None = None
    serialNumber: str | None = None
    batchId: str | None = None
    globalAssetId: str | None = None
    gtin: str | None = Field(
        default=None,
        description="GS1 GTIN (8/12/13/14 digits). Validated via check digit.",
    )

    @field_validator("gtin")
    @classmethod
    def validate_gtin_check_digit(cls, v: str | None) -> str | None:
        if v is None:
            return v
        from app.modules.qr.service import QRCodeService
        if not QRCodeService.validate_gtin(v):
            raise ValueError(f"GTIN '{v}' has an invalid check digit")
        return v
```

Add `field_validator` to the imports at the top of `router.py` (add to the existing pydantic import line).

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_opcua_gtin.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/app/modules/dpps/router.py backend/tests/test_opcua_gtin.py
git commit -m "feat(gtin): add gtin field to AssetIdsInput with check digit validation"
```

---

### Task 9: Digital Link endpoint

**Files:**
- Modify: `backend/app/modules/dpps/router.py` (add `/digital-link` endpoint)
- Test: `backend/tests/test_opcua_digital_link.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_opcua_digital_link.py
"""Tests for the /digital-link endpoint."""

import pytest


def test_build_digital_link_uri():
    """Build canonical GS1 Digital Link from GTIN + serial."""
    from app.modules.dpps.router import _build_digital_link_uri

    uri = _build_digital_link_uri(
        resolver_base_url="https://id.example.com",
        gtin="4006381333931",
        serial="SN-001",
    )
    assert uri == "https://id.example.com/01/4006381333931/21/SN-001"


def test_build_digital_link_uri_no_serial():
    """Digital Link without serial number."""
    from app.modules.dpps.router import _build_digital_link_uri

    uri = _build_digital_link_uri(
        resolver_base_url="https://id.example.com",
        gtin="4006381333931",
    )
    assert uri == "https://id.example.com/01/4006381333931"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_opcua_digital_link.py -v`
Expected: FAIL with `ImportError`

**Step 3: Add helper and endpoint**

Add to `backend/app/modules/dpps/router.py` (before the endpoint functions):

```python
def _build_digital_link_uri(
    resolver_base_url: str,
    gtin: str,
    serial: str | None = None,
) -> str:
    """Build a canonical GS1 Digital Link URI."""
    base = resolver_base_url.rstrip("/")
    uri = f"{base}/01/{gtin}"
    if serial:
        uri += f"/21/{serial}"
    return uri
```

Then add the endpoint:

```python
@router.get(
    "/dpps/{dpp_id}/digital-link",
    summary="Get GS1 Digital Link URI for a DPP",
)
async def get_dpp_digital_link(
    dpp_id: UUID,
    request: Request,
    tenant: TenantPublisher = Depends(),
    db: AsyncSession = Depends(get_db_session),
):
    """Return the canonical GS1 Digital Link URI for a DPP with GTIN."""
    dpp = await _get_dpp_or_404(dpp_id, tenant, db, request, action="read")
    asset_ids = dpp.asset_ids or {}
    gtin = asset_ids.get("gtin")
    if not gtin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DPP has no GTIN in asset identifiers",
        )
    serial = asset_ids.get("serialNumber")
    settings = get_settings()
    resolver_base = settings.resolver_base_url or f"https://{request.headers.get('host', 'localhost')}"
    uri = _build_digital_link_uri(resolver_base, gtin, serial)
    return {
        "digital_link_uri": uri,
        "gtin": gtin,
        "serial_number": serial,
        "is_pseudo_gtin": gtin.startswith("0200"),
    }
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_opcua_digital_link.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/app/modules/dpps/router.py backend/tests/test_opcua_digital_link.py
git commit -m "feat(gtin): add /digital-link endpoint with GS1 URI generation"
```

---

## Phase 9: Dataspace Publication

### Task 10: Dataspace schemas

**Files:**
- Modify: `backend/app/modules/opcua/schemas.py` (add 3 schemas)
- Test: `backend/tests/test_opcua_dataspace_schemas.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_opcua_dataspace_schemas.py
"""Tests for dataspace publication schemas."""

import uuid

import pytest


def test_dataspace_publish_request():
    """DataspacePublishRequest should accept valid input."""
    from app.modules.opcua.schemas import DataspacePublishRequest

    req = DataspacePublishRequest(dpp_id=uuid.uuid4(), target="catena-x")
    assert req.target == "catena-x"


def test_dataspace_publication_job_response():
    """DataspacePublicationJobResponse should load from ORM attributes."""
    from app.modules.opcua.schemas import DataspacePublicationJobResponse

    # Test model_config has from_attributes
    assert DataspacePublicationJobResponse.model_config.get("from_attributes") is True
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_opcua_dataspace_schemas.py -v`
Expected: FAIL with `ImportError`

**Step 3: Add schemas to `schemas.py`**

Append to `backend/app/modules/opcua/schemas.py`:

```python
# ---------------------------------------------------------------------------
# Dataspace Publication
# ---------------------------------------------------------------------------


class DataspacePublishRequest(BaseModel):
    """Request to publish a DPP to a dataspace (DTR + EDC)."""

    model_config = ConfigDict(populate_by_name=True)

    dpp_id: UUID = Field(alias="dppId")
    target: str = Field(default="catena-x", description="Target ecosystem")


class DataspacePublicationJobResponse(BaseModel):
    """Dataspace publication job summary."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    dpp_id: UUID
    status: str
    target: str
    artifact_refs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class DataspacePublicationJobListResponse(BaseModel):
    """Paginated list of publication jobs."""

    items: list[DataspacePublicationJobResponse]
    total: int
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_opcua_dataspace_schemas.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/app/modules/opcua/schemas.py backend/tests/test_opcua_dataspace_schemas.py
git commit -m "feat(dataspace): add publication job schemas"
```

---

### Task 11: Dataspace service

**Files:**
- Create: `backend/app/modules/opcua/dataspace.py`
- Test: `backend/tests/test_opcua_dataspace_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_opcua_dataspace_service.py
"""Tests for the dataspace publication service."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import DataspacePublicationStatus


@pytest.mark.asyncio
async def test_create_publication_job():
    """create_publication_job should insert a queued job."""
    from app.modules.opcua.dataspace import DataspacePublicationService

    mock_session = AsyncMock()
    mock_session.flush = AsyncMock()

    svc = DataspacePublicationService(mock_session)
    job = await svc.create_publication_job(
        tenant_id=uuid.uuid4(),
        dpp_id=uuid.uuid4(),
        target="catena-x",
    )

    assert job.status == DataspacePublicationStatus.QUEUED
    assert job.target == "catena-x"
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_publication_job():
    """get_publication_job should return a job by ID."""
    from app.modules.opcua.dataspace import DataspacePublicationService

    mock_session = AsyncMock()
    mock_job = MagicMock()
    mock_job.tenant_id = uuid.uuid4()
    mock_session.get.return_value = mock_job

    svc = DataspacePublicationService(mock_session)
    result = await svc.get_publication_job(uuid.uuid4(), mock_job.tenant_id)
    assert result is mock_job
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_opcua_dataspace_service.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# backend/app/modules/opcua/dataspace.py
"""Dataspace publication service — DTR + EDC publication workflow.

Manages the publication of DPPs to dataspace components (Digital Twin
Registry, Eclipse Dataspace Connector) as Catena-X digital twins.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DataspacePublicationJob,
    DataspacePublicationStatus,
)

logger = logging.getLogger(__name__)


class DataspacePublicationService:
    """Manages publication job lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_publication_job(
        self,
        tenant_id: UUID,
        dpp_id: UUID,
        target: str = "catena-x",
    ) -> DataspacePublicationJob:
        """Create a new publication job in QUEUED state."""
        job = DataspacePublicationJob(
            tenant_id=tenant_id,
            dpp_id=dpp_id,
            status=DataspacePublicationStatus.QUEUED,
            target=target,
            artifact_refs={},
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def get_publication_job(
        self,
        job_id: UUID,
        tenant_id: UUID,
    ) -> DataspacePublicationJob | None:
        """Get a publication job by ID within a tenant."""
        job = await self._session.get(DataspacePublicationJob, job_id)
        if job and str(job.tenant_id) == str(tenant_id):
            return job
        return None

    async def list_publication_jobs(
        self,
        tenant_id: UUID,
        *,
        dpp_id: UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[DataspacePublicationJob], int]:
        """List publication jobs for a tenant, optionally filtered by DPP."""
        base = select(DataspacePublicationJob).where(
            DataspacePublicationJob.tenant_id == tenant_id,
        )
        if dpp_id:
            base = base.where(DataspacePublicationJob.dpp_id == dpp_id)

        count_q = select(func.count()).select_from(base.subquery())
        total = (await self._session.execute(count_q)).scalar_one()

        rows_q = base.order_by(DataspacePublicationJob.created_at.desc()).offset(offset).limit(limit)
        rows = (await self._session.execute(rows_q)).scalars().all()
        return list(rows), total

    async def retry_publication_job(
        self,
        job: DataspacePublicationJob,
    ) -> DataspacePublicationJob:
        """Reset a failed job back to QUEUED for retry."""
        if job.status != DataspacePublicationStatus.FAILED:
            raise ValueError("Only failed jobs can be retried")
        job.status = DataspacePublicationStatus.QUEUED
        job.error = None
        await self._session.flush()
        return job
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_opcua_dataspace_service.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/app/modules/opcua/dataspace.py backend/tests/test_opcua_dataspace_service.py
git commit -m "feat(dataspace): add publication job service"
```

---

### Task 12: Dataspace endpoints in router

**Files:**
- Modify: `backend/app/modules/opcua/router.py` (add 4 endpoints)
- Test: verify imports work

**Step 1: Add dataspace endpoints to `router.py`**

Add at the end of `backend/app/modules/opcua/router.py`:

```python
# ---------------------------------------------------------------------------
# Dataspace publication
# ---------------------------------------------------------------------------

from .dataspace import DataspacePublicationService
from .schemas import (
    DataspacePublicationJobListResponse,
    DataspacePublicationJobResponse,
    DataspacePublishRequest,
)


@router.post(
    "/dataspace/publish",
    response_model=DataspacePublicationJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Queue a DPP for dataspace publication",
)
async def publish_to_dataspace(
    body: DataspacePublishRequest,
    request: Request,
    tenant: TenantPublisher,
    db: DbSession,
) -> DataspacePublicationJobResponse:
    _require_opcua_enabled()
    # Verify DPP exists and user has publish access
    from app.modules.dpps.service import DPPService

    dpp_svc = DPPService(db)
    dpp = await dpp_svc.get_dpp(body.dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {body.dpp_id} not found",
        )

    ds_svc = DataspacePublicationService(db)
    job = await ds_svc.create_publication_job(
        tenant_id=tenant.tenant_id,
        dpp_id=body.dpp_id,
        target=body.target,
    )
    await emit_audit_event(
        db,
        tenant_id=str(tenant.tenant_id),
        actor=tenant.user.sub,
        action="dataspace.publish.queued",
        resource_type="dataspace_publication_job",
        resource_id=str(job.id),
        details={"dpp_id": str(body.dpp_id), "target": body.target},
    )
    return DataspacePublicationJobResponse.model_validate(job)


@router.get(
    "/dataspace/jobs",
    response_model=DataspacePublicationJobListResponse,
    summary="List dataspace publication jobs",
)
async def list_publication_jobs(
    request: Request,
    tenant: TenantPublisher,
    db: DbSession,
    dpp_id: UUID | None = Query(default=None, alias="dppId"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> DataspacePublicationJobListResponse:
    _require_opcua_enabled()
    ds_svc = DataspacePublicationService(db)
    items, total = await ds_svc.list_publication_jobs(
        tenant.tenant_id,
        dpp_id=dpp_id,
        offset=offset,
        limit=limit,
    )
    return DataspacePublicationJobListResponse(
        items=[DataspacePublicationJobResponse.model_validate(j) for j in items],
        total=total,
    )


@router.get(
    "/dataspace/jobs/{job_id}",
    response_model=DataspacePublicationJobResponse,
    summary="Get a publication job",
)
async def get_publication_job(
    job_id: UUID,
    request: Request,
    tenant: TenantPublisher,
    db: DbSession,
) -> DataspacePublicationJobResponse:
    _require_opcua_enabled()
    ds_svc = DataspacePublicationService(db)
    job = await ds_svc.get_publication_job(job_id, tenant.tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publication job {job_id} not found",
        )
    return DataspacePublicationJobResponse.model_validate(job)


@router.post(
    "/dataspace/jobs/{job_id}/retry",
    response_model=DataspacePublicationJobResponse,
    summary="Retry a failed publication job",
)
async def retry_publication_job(
    job_id: UUID,
    request: Request,
    tenant: TenantPublisher,
    db: DbSession,
) -> DataspacePublicationJobResponse:
    _require_opcua_enabled()
    ds_svc = DataspacePublicationService(db)
    job = await ds_svc.get_publication_job(job_id, tenant.tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publication job {job_id} not found",
        )
    try:
        job = await ds_svc.retry_publication_job(job)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await emit_audit_event(
        db,
        tenant_id=str(tenant.tenant_id),
        actor=tenant.user.sub,
        action="dataspace.publish.retried",
        resource_type="dataspace_publication_job",
        resource_id=str(job.id),
        details={"dpp_id": str(job.dpp_id)},
    )
    return DataspacePublicationJobResponse.model_validate(job)
```

**Step 2: Verify module imports**

Run: `cd backend && uv run python -c "from app.modules.opcua.router import router; print('OK:', len(router.routes), 'routes')"`
Expected: `OK: 23 routes` (19 original + 4 new)

**Step 3: Commit**

```bash
git add backend/app/modules/opcua/router.py backend/app/modules/opcua/schemas.py
git commit -m "feat(dataspace): add 4 publication endpoints to OPC UA router"
```

---

## Phase 10: EPCIS Event Triggers

### Task 13: EPCIS emitter for agent

**Files:**
- Create: `backend/app/opcua_agent/epcis_emitter.py`
- Test: `backend/tests/test_opcua_epcis_emitter.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_opcua_epcis_emitter.py
"""Tests for the EPCIS event emitter."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.opcua_agent.epcis_emitter import build_epcis_event_payload


def test_build_epcis_event_payload():
    """Build an EPCIS ObjectEvent payload from mapping config."""
    payload = build_epcis_event_payload(
        event_type="ObjectEvent",
        biz_step="urn:epcglobal:cbv:bizstep:inspecting",
        disposition="urn:epcglobal:cbv:disp:in_progress",
        action="OBSERVE",
        read_point="urn:epc:id:sgln:9521234.00001.0",
        biz_location="urn:epc:id:sgln:9521234.00000.0",
        epc_list=["urn:epc:id:sgtin:9521234.00001.1001"],
        event_time=datetime(2026, 2, 19, 12, 0, 0, tzinfo=UTC),
    )

    assert payload["type"] == "ObjectEvent"
    assert payload["bizStep"] == "urn:epcglobal:cbv:bizstep:inspecting"
    assert payload["action"] == "OBSERVE"
    assert len(payload["epcList"]) == 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_opcua_epcis_emitter.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# backend/app/opcua_agent/epcis_emitter.py
"""EPCIS event emitter — creates EPCIS events from OPC UA triggers.

When a mapping with mapping_type=EPCIS_EVENT fires, this module
constructs an EPCIS event payload and persists it via EPCISService.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("opcua_agent.epcis")


def build_epcis_event_payload(
    *,
    event_type: str,
    biz_step: str | None = None,
    disposition: str | None = None,
    action: str = "OBSERVE",
    read_point: str | None = None,
    biz_location: str | None = None,
    epc_list: list[str] | None = None,
    event_time: datetime | None = None,
    source_event_id: str | None = None,
) -> dict[str, Any]:
    """Build a minimal EPCIS event dict from mapping configuration.

    The returned dict follows the GS1 EPCIS 2.0 JSON-LD structure.
    """
    now = event_time or datetime.now(tz=UTC)
    event: dict[str, Any] = {
        "type": event_type,
        "eventTime": now.isoformat(),
        "eventTimeZoneOffset": "+00:00",
        "action": action,
    }

    if biz_step:
        event["bizStep"] = biz_step
    if disposition:
        event["disposition"] = disposition
    if read_point:
        event["readPoint"] = {"id": read_point}
    if biz_location:
        event["bizLocation"] = {"id": biz_location}
    if epc_list:
        event["epcList"] = list(epc_list)
    if source_event_id:
        event["sourceEventId"] = source_event_id

    return event
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_opcua_epcis_emitter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/opcua_agent/epcis_emitter.py backend/tests/test_opcua_epcis_emitter.py
git commit -m "feat(epcis): add EPCIS event payload builder for OPC UA triggers"
```

---

### Task 14: EPCIS idempotency migration

**Files:**
- Create: `backend/app/db/migrations/versions/0042_epcis_source_event_id_uniqueness.py`
- Test: Verify migration applies cleanly

**Step 1: Write the migration**

```python
# backend/app/db/migrations/versions/0042_epcis_source_event_id_uniqueness.py
"""Add partial unique index for EPCIS source_event_id idempotency.

Revision ID: 0042epcisidempotency
Revises: <PREVIOUS_HEAD>
Create Date: 2026-02-19
"""

from alembic import op

# revision identifiers
revision = "0042epcisidempotency"
down_revision = None  # Will be set during implementation to actual previous head
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add source_event_id column to epcis_events if not present
    op.add_column(
        "epcis_events",
        sa.Column("source_event_id", sa.String(255), nullable=True),
    )
    # Partial unique index — only enforced where source_event_id IS NOT NULL
    op.create_index(
        "ix_epcis_events_source_event_id_unique",
        "epcis_events",
        ["tenant_id", "source_event_id"],
        unique=True,
        postgresql_where=sa.text("source_event_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_epcis_events_source_event_id_unique", table_name="epcis_events")
    op.drop_column("epcis_events", "source_event_id")
```

> **Note to implementer:** Before creating this migration, run `cd backend && uv run alembic heads` to get the current head revision and set `down_revision` accordingly. Also add `import sqlalchemy as sa` at the top.

**Step 2: Apply migration**

Run: `cd backend && uv run alembic upgrade head`
Expected: Migration applies without errors.

**Step 3: Verify reversibility**

Run: `cd backend && uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: Both succeed.

**Step 4: Commit**

```bash
git add backend/app/db/migrations/versions/0042_epcis_source_event_id_uniqueness.py
git commit -m "feat(epcis): add partial unique index for source_event_id idempotency"
```

---

## Phase 11: Observability & Secrets Hardening

### Task 15: Health server

**Files:**
- Create: `backend/app/opcua_agent/health.py`
- Test: `backend/tests/test_opcua_health.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_opcua_health.py
"""Tests for the agent health server."""

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, TestClient, TestServer

from app.opcua_agent.health import create_health_app


@pytest.mark.asyncio
async def test_healthz_returns_ok():
    """GET /healthz should return 200."""
    app = create_health_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/healthz")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_readyz_returns_ok():
    """GET /readyz should return 200."""
    app = create_health_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/readyz")
        assert resp.status == 200
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_opcua_health.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# backend/app/opcua_agent/health.py
"""Health and metrics server for the OPC UA agent.

Exposes /healthz, /readyz, and /metrics endpoints on a configurable
port (default 8090) for container orchestration and Prometheus scraping.
"""

from __future__ import annotations

import logging

from aiohttp import web
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger("opcua_agent.health")

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

REGISTRY = CollectorRegistry()

CONNECTIONS_ACTIVE = Gauge(
    "opcua_agent_connections_active",
    "Active OPC UA connections",
    registry=REGISTRY,
)
SUBSCRIPTIONS_ACTIVE = Gauge(
    "opcua_agent_subscriptions_active",
    "Active OPC UA subscriptions",
    registry=REGISTRY,
)
BUFFER_SIZE = Gauge(
    "opcua_agent_buffer_size",
    "Current ingestion buffer depth",
    registry=REGISTRY,
)
FLUSH_TOTAL = Counter(
    "opcua_agent_flush_total",
    "Total flush cycles completed",
    registry=REGISTRY,
)
FLUSH_DURATION = Histogram(
    "opcua_agent_flush_duration_seconds",
    "Flush cycle duration",
    registry=REGISTRY,
)
FLUSH_ERRORS = Counter(
    "opcua_agent_flush_errors_total",
    "Total flush errors",
    registry=REGISTRY,
)
DATA_CHANGES_TOTAL = Counter(
    "opcua_agent_data_changes_total",
    "Total OPC UA data change notifications received",
    registry=REGISTRY,
)
TRANSFORM_ERRORS = Counter(
    "opcua_agent_transform_errors_total",
    "Total transform failures",
    registry=REGISTRY,
)
DEAD_LETTERS_TOTAL = Counter(
    "opcua_agent_dead_letters_total",
    "Total dead letter records created",
    registry=REGISTRY,
)
RECONNECTS_TOTAL = Counter(
    "opcua_agent_reconnects_total",
    "Total OPC UA reconnection attempts",
    registry=REGISTRY,
)


# ---------------------------------------------------------------------------
# aiohttp app
# ---------------------------------------------------------------------------


def create_health_app() -> web.Application:
    """Create aiohttp app with health and metrics endpoints."""
    app = web.Application()
    app.router.add_get("/healthz", _healthz)
    app.router.add_get("/readyz", _readyz)
    app.router.add_get("/metrics", _metrics)
    return app


async def _healthz(request: web.Request) -> web.Response:
    """Liveness probe — always returns 200 if the process is alive."""
    return web.json_response({"status": "ok"})


async def _readyz(request: web.Request) -> web.Response:
    """Readiness probe — returns 200 if the agent is operational."""
    return web.json_response({"status": "ready"})


async def _metrics(request: web.Request) -> web.Response:
    """Prometheus metrics endpoint."""
    body = generate_latest(REGISTRY)
    return web.Response(body=body, content_type="text/plain; version=0.0.4")
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_opcua_health.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/app/opcua_agent/health.py backend/tests/test_opcua_health.py
git commit -m "feat(opcua): add health server with Prometheus metrics"
```

---

### Task 16: Wire health server into agent main loop

**Files:**
- Modify: `backend/app/opcua_agent/main.py` (start health server)

**Step 1: Update `main.py` to start health server**

In `run_agent()`, add after the signal handlers and before the main loop:

```python
    # Start health server
    from app.opcua_agent.health import create_health_app

    health_app = create_health_app()
    health_runner = web.AppRunner(health_app)
    await health_runner.setup()
    health_site = web.TCPSite(health_runner, "0.0.0.0", 8090)
    await health_site.start()
    logger.info("Health server started on port 8090")
```

Add to the `finally` block:

```python
        await health_runner.cleanup()
```

Add import at top of file:

```python
from aiohttp import web
```

**Step 2: Run all agent tests**

Run: `cd backend && uv run pytest tests/test_opcua_agent_main.py tests/test_opcua_health.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add backend/app/opcua_agent/main.py
git commit -m "feat(opcua): wire health server into agent main loop"
```

---

### Task 17: Final integration verification

**Step 1: Lint all new files**

Run: `cd backend && uv run ruff check app/opcua_agent/ app/modules/opcua/ --fix`
Expected: No errors (or auto-fixed).

Run: `cd backend && uv run ruff format app/opcua_agent/ app/modules/opcua/`
Expected: Files formatted.

**Step 2: Type check**

Run: `cd backend && uv run mypy app/opcua_agent/ app/modules/opcua/ --ignore-missing-imports`
Expected: No errors.

**Step 3: Run all OPC UA tests**

Run: `cd backend && uv run pytest tests/test_opcua*.py -v`
Expected: ALL PASS (should be ~15 tests across all files).

**Step 4: Verify module loads**

Run: `cd backend && uv run python -c "from app.modules.opcua.router import router; print('Routes:', len(router.routes))"`
Expected: `Routes: 23`

Run: `cd backend && uv run python -c "from app.opcua_agent.main import run_agent; print('Agent: OK')"`
Expected: `Agent: OK`

**Step 5: Verify transform DSL still passes**

Run:
```bash
cd backend && uv run python -c "
from app.modules.opcua.transform import apply_transform, validate_transform_expr
assert apply_transform('scale:0.001|round:2', 12345) == 12.35
assert apply_transform('cast:string', 42) == '42'
assert validate_transform_expr('scale:abc') != []
print('Transform DSL: all assertions passed')
"
```
Expected: `Transform DSL: all assertions passed`

**Step 6: Commit lint/format fixes if any**

```bash
git add -A
git commit -m "chore(opcua): lint and format phases 7-11 code"
```

---

## File Summary

| # | File | Status | Task |
|---|------|--------|------|
| 0 | `backend/pyproject.toml` | Modify | Task 0 |
| 1 | `backend/app/opcua_agent/__init__.py` | Create | Task 1 |
| 2 | `backend/app/opcua_agent/__main__.py` | Create | Task 1 |
| 3 | `backend/app/opcua_agent/main.py` | Create | Task 1, 7, 16 |
| 4 | `backend/app/opcua_agent/ingestion_buffer.py` | Create | Task 2 |
| 5 | `backend/app/opcua_agent/deadletter.py` | Create | Task 3 |
| 6 | `backend/app/opcua_agent/flush_engine.py` | Create | Task 4 |
| 7 | `backend/app/opcua_agent/connection_manager.py` | Create | Task 5 |
| 8 | `backend/app/opcua_agent/subscription_handler.py` | Create | Task 6 |
| 9 | `backend/app/opcua_agent/health.py` | Create | Task 15 |
| 10 | `backend/app/opcua_agent/epcis_emitter.py` | Create | Task 13 |
| 11 | `backend/app/modules/dpps/router.py` | Modify | Task 8, 9 |
| 12 | `backend/app/modules/opcua/schemas.py` | Modify | Task 10 |
| 13 | `backend/app/modules/opcua/dataspace.py` | Create | Task 11 |
| 14 | `backend/app/modules/opcua/router.py` | Modify | Task 12 |
| 15 | `backend/app/db/migrations/versions/0042_*.py` | Create | Task 14 |
| 16 | `docker-compose.yml` | Modify | Task 7 |

**Total: 11 new files, 5 modified files, ~1,280 new lines**

## Test Files

| File | Tests |
|------|-------|
| `backend/tests/test_opcua_agent_main.py` | 1 |
| `backend/tests/test_opcua_ingestion_buffer.py` | 3 |
| `backend/tests/test_opcua_deadletter.py` | 1 |
| `backend/tests/test_opcua_flush_engine.py` | 2 |
| `backend/tests/test_opcua_connection_manager.py` | 2 |
| `backend/tests/test_opcua_subscription_handler.py` | 2 |
| `backend/tests/test_opcua_gtin.py` | 3 |
| `backend/tests/test_opcua_digital_link.py` | 2 |
| `backend/tests/test_opcua_dataspace_schemas.py` | 2 |
| `backend/tests/test_opcua_dataspace_service.py` | 2 |
| `backend/tests/test_opcua_epcis_emitter.py` | 1 |
| `backend/tests/test_opcua_health.py` | 2 |

**Total: 23 tests across 12 test files**
