"""Tests for audit router helper functions."""

from __future__ import annotations

from app.modules.audit.router import _get_crypto_attr, _has_hash_columns


class TestHasHashColumns:
    """Tests for column detection in router."""

    def test_with_migration(self) -> None:
        """After migration 0011, the model has hash chain columns."""
        assert _has_hash_columns() is True


class TestGetCryptoAttr:
    """Tests for safe attribute access helper."""

    def test_existing_attr(self) -> None:
        class FakeEvent:
            event_hash = "abc123"

        result = _get_crypto_attr(FakeEvent(), "event_hash")  # type: ignore[arg-type]
        assert result == "abc123"

    def test_missing_attr(self) -> None:
        class FakeEvent:
            pass

        result = _get_crypto_attr(FakeEvent(), "event_hash")  # type: ignore[arg-type]
        assert result is None


class TestAuditSchemas:
    """Tests for audit Pydantic schemas."""

    def test_audit_event_response_minimal(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.modules.audit.schemas import AuditEventResponse

        resp = AuditEventResponse(
            id=uuid4(),
            action="create_dpp",
            resource_type="dpp",
            created_at=datetime.now(UTC),
        )
        assert resp.event_hash is None
        assert resp.chain_sequence is None

    def test_chain_verification_response(self) -> None:
        from uuid import uuid4

        from app.modules.audit.schemas import ChainVerificationResponse

        resp = ChainVerificationResponse(
            is_valid=True,
            verified_count=10,
            errors=[],
            tenant_id=uuid4(),
        )
        assert resp.is_valid
        assert resp.first_break_at is None

    def test_anchor_response(self) -> None:
        from uuid import uuid4

        from app.modules.audit.schemas import AnchorResponse

        anchor_id = uuid4()
        resp = AnchorResponse(
            anchor_id=anchor_id,
            merkle_root="a" * 64,
            event_count=100,
            first_sequence=0,
            last_sequence=99,
            signature_kid="audit-key-1",
            tenant_id=uuid4(),
        )
        assert resp.anchor_id == anchor_id
        assert resp.signature is None
        assert resp.signature_kid == "audit-key-1"
        assert resp.tsa_token_present is False

    def test_event_list_response(self) -> None:
        from app.modules.audit.schemas import AuditEventListResponse

        resp = AuditEventListResponse(
            items=[],
            total=0,
            page=1,
            page_size=50,
        )
        assert resp.total == 0
        assert resp.items == []
