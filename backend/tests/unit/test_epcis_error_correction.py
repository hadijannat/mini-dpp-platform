"""Unit tests for EPCIS error correction validation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.modules.epcis.schemas import (
    EPCISDocumentCreate,
    ErrorDeclaration,
    ObjectEventCreate,
)
from app.modules.epcis.service import EPCISService

NOW = datetime(2026, 2, 7, 10, 0, 0, tzinfo=UTC)
NOW_ISO = "2026-02-07T10:00:00+00:00"


# ---------------------------------------------------------------------------
# Schema-level tests for ErrorDeclaration
# ---------------------------------------------------------------------------


class TestErrorDeclarationSchema:
    def test_valid_error_declaration(self) -> None:
        data = {
            "type": "ObjectEvent",
            "eventTime": NOW_ISO,
            "eventTimeZoneOffset": "+00:00",
            "action": "OBSERVE",
            "errorDeclaration": {
                "declarationTime": NOW_ISO,
                "reason": "incorrect_data",
                "correctiveEventIDs": ["urn:uuid:abc-123", "urn:uuid:def-456"],
            },
        }
        event = ObjectEventCreate.model_validate(data)
        assert event.error_declaration is not None
        assert len(event.error_declaration.corrective_event_ids) == 2

    def test_error_declaration_without_corrective_ids(self) -> None:
        data = {
            "type": "ObjectEvent",
            "eventTime": NOW_ISO,
            "eventTimeZoneOffset": "+00:00",
            "action": "OBSERVE",
            "errorDeclaration": {
                "declarationTime": NOW_ISO,
                "reason": "did_not_occur",
            },
        }
        event = ObjectEventCreate.model_validate(data)
        assert event.error_declaration is not None
        assert event.error_declaration.corrective_event_ids == []

    def test_error_declaration_roundtrip(self) -> None:
        decl = ErrorDeclaration(
            declaration_time=NOW,
            reason="incorrect_data",
            corrective_event_ids=["urn:uuid:abc"],
        )
        dumped = decl.model_dump(by_alias=True, mode="json")
        assert "declarationTime" in dumped
        assert "correctiveEventIDs" in dumped
        assert dumped["correctiveEventIDs"] == ["urn:uuid:abc"]


# ---------------------------------------------------------------------------
# Service-level validation (mocked DB)
# ---------------------------------------------------------------------------


class _FakeScalarsResult:
    """Minimal fake for SQLAlchemy result.scalars()."""

    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def scalars(self) -> _FakeScalarsResult:
        return self

    def all(self) -> list[Any]:
        return self._values


class _FakeSession:
    """Minimal async session mock for testing _validate_corrective_event_ids."""

    def __init__(self, found_event_ids: list[str]) -> None:
        self._found_event_ids = found_event_ids

    async def execute(self, _stmt: object) -> _FakeScalarsResult:
        return _FakeScalarsResult(self._found_event_ids)

    async def flush(self) -> None:
        pass

    def add(self, _obj: object) -> None:
        pass


def _make_document(corrective_ids: list[str]) -> EPCISDocumentCreate:
    return EPCISDocumentCreate.model_validate(
        {
            "@context": ["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
            "type": "EPCISDocument",
            "schemaVersion": "2.0",
            "creationDate": NOW_ISO,
            "epcisBody": {
                "eventList": [
                    {
                        "type": "ObjectEvent",
                        "eventTime": NOW_ISO,
                        "eventTimeZoneOffset": "+00:00",
                        "action": "OBSERVE",
                        "errorDeclaration": {
                            "declarationTime": NOW_ISO,
                            "reason": "incorrect_data",
                            "correctiveEventIDs": corrective_ids,
                        },
                    }
                ]
            },
        }
    )


class TestErrorCorrectionValidation:
    @pytest.mark.asyncio
    async def test_valid_corrective_ids_passes(self) -> None:
        """Capture should succeed when all corrective event IDs exist."""
        from uuid import uuid4

        session = _FakeSession(found_event_ids=["urn:uuid:existing-1"])
        service = EPCISService(session)  # type: ignore[arg-type]

        doc = _make_document(["urn:uuid:existing-1"])
        result = await service.capture(
            tenant_id=uuid4(),
            dpp_id=uuid4(),
            document=doc,
            created_by="test-user",
        )
        assert result.event_count == 1

    @pytest.mark.asyncio
    async def test_missing_corrective_ids_raises(self) -> None:
        """Capture should raise ValueError when corrective IDs are not found."""
        from uuid import uuid4

        session = _FakeSession(found_event_ids=[])
        service = EPCISService(session)  # type: ignore[arg-type]

        doc = _make_document(["urn:uuid:nonexistent"])
        with pytest.raises(ValueError, match="Corrective event IDs not found"):
            await service.capture(
                tenant_id=uuid4(),
                dpp_id=uuid4(),
                document=doc,
                created_by="test-user",
            )

    @pytest.mark.asyncio
    async def test_partial_missing_raises(self) -> None:
        """If some corrective IDs exist but others don't, raise ValueError."""
        from uuid import uuid4

        session = _FakeSession(found_event_ids=["urn:uuid:exists"])
        service = EPCISService(session)  # type: ignore[arg-type]

        doc = _make_document(["urn:uuid:exists", "urn:uuid:missing"])
        with pytest.raises(ValueError, match="urn:uuid:missing"):
            await service.capture(
                tenant_id=uuid4(),
                dpp_id=uuid4(),
                document=doc,
                created_by="test-user",
            )

    @pytest.mark.asyncio
    async def test_no_error_declaration_passes(self) -> None:
        """Capture without error_declaration should succeed without validation."""
        from uuid import uuid4

        session = _FakeSession(found_event_ids=[])
        service = EPCISService(session)  # type: ignore[arg-type]

        doc = EPCISDocumentCreate.model_validate(
            {
                "@context": ["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
                "type": "EPCISDocument",
                "schemaVersion": "2.0",
                "creationDate": NOW_ISO,
                "epcisBody": {
                    "eventList": [
                        {
                            "type": "ObjectEvent",
                            "eventTime": NOW_ISO,
                            "eventTimeZoneOffset": "+00:00",
                            "action": "ADD",
                        }
                    ]
                },
            }
        )
        result = await service.capture(
            tenant_id=uuid4(),
            dpp_id=uuid4(),
            document=doc,
            created_by="test-user",
        )
        assert result.event_count == 1
