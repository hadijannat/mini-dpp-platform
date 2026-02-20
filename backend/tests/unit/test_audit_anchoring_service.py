"""Unit tests for audit anchoring service."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db.models import AuditEvent
from app.modules.audit.anchoring_service import AuditAnchoringService


def _scalar_one_or_none(value: object | None) -> object:
    return SimpleNamespace(scalar_one_or_none=lambda: value)


def _scalars_all(values: list[object]) -> object:
    return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: values))


def _make_event(*, tenant_id: object, sequence: int, event_hash: str) -> AuditEvent:
    return AuditEvent(
        tenant_id=tenant_id,
        action="update_dpp",
        resource_type="dpp",
        chain_sequence=sequence,
        event_hash=event_hash,
        prev_event_hash="0" * 64,
    )


@pytest.mark.asyncio
@patch("app.modules.audit.anchoring_service.request_timestamp", new_callable=AsyncMock)
@patch("app.modules.audit.anchoring_service.sign_merkle_root")
async def test_anchor_next_batch_persists_signature_and_tsa_metadata(
    mock_sign_merkle_root: MagicMock,
    mock_request_timestamp: AsyncMock,
) -> None:
    tenant_id = uuid4()
    events = [
        _make_event(tenant_id=tenant_id, sequence=1, event_hash="a" * 64),
        _make_event(tenant_id=tenant_id, sequence=2, event_hash="b" * 64),
    ]

    session = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_one_or_none(None),  # no prior anchors
            _scalars_all(events),
        ]
    )
    session.add = MagicMock()

    settings = SimpleNamespace(
        audit_signing_key="-----BEGIN PRIVATE KEY-----\nTEST\n-----END PRIVATE KEY-----",
        audit_signing_key_id="audit-kid-1",
        audit_merkle_batch_size=100,
        tsa_url="https://tsa.example.com",
    )
    mock_sign_merkle_root.return_value = "signed-root"
    mock_request_timestamp.return_value = b"tsa-token"

    service = AuditAnchoringService(session, settings=settings)
    anchor = await service.anchor_next_batch(tenant_id=tenant_id)

    assert anchor is not None
    assert anchor.event_count == 2
    assert anchor.first_sequence == 1
    assert anchor.last_sequence == 2
    assert anchor.signature == "signed-root"
    assert anchor.signature_kid == "audit-kid-1"
    assert anchor.signature_algorithm == "Ed25519"
    assert anchor.tsa_token == b"tsa-token"
    assert anchor.timestamp_hash_algorithm == "sha-256"

    session.add.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.modules.audit.anchoring_service.sign_merkle_root")
async def test_anchor_next_batch_without_tsa_url_leaves_timestamp_metadata_empty(
    mock_sign_merkle_root: MagicMock,
) -> None:
    tenant_id = uuid4()
    events = [_make_event(tenant_id=tenant_id, sequence=7, event_hash="c" * 64)]

    session = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_one_or_none(None),
            _scalars_all(events),
        ]
    )
    session.add = MagicMock()

    settings = SimpleNamespace(
        audit_signing_key="-----BEGIN PRIVATE KEY-----\nTEST\n-----END PRIVATE KEY-----",
        audit_signing_key_id="audit-kid-2",
        audit_merkle_batch_size=100,
        tsa_url="",
    )
    mock_sign_merkle_root.return_value = "signed-root"

    service = AuditAnchoringService(session, settings=settings)
    anchor = await service.anchor_next_batch(tenant_id=tenant_id)

    assert anchor is not None
    assert anchor.tsa_token is None
    assert anchor.timestamp_hash_algorithm is None


@pytest.mark.asyncio
async def test_anchor_next_batch_returns_none_when_no_pending_events() -> None:
    tenant_id = uuid4()
    session = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_one_or_none(3),
            _scalars_all([]),
        ]
    )
    session.add = MagicMock()

    settings = SimpleNamespace(
        audit_signing_key="-----BEGIN PRIVATE KEY-----\nTEST\n-----END PRIVATE KEY-----",
        audit_signing_key_id="audit-kid-3",
        audit_merkle_batch_size=100,
        tsa_url="",
    )

    service = AuditAnchoringService(session, settings=settings)
    anchor = await service.anchor_next_batch(tenant_id=tenant_id)

    assert anchor is None
    session.add.assert_not_called()
    session.flush.assert_not_awaited()
