"""Unit tests for EPCIS named query schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.epcis.schemas import (
    EPCISQueryParams,
    NamedQueryCreate,
    NamedQueryResponse,
)

# ---------------------------------------------------------------------------
# NamedQueryCreate validation
# ---------------------------------------------------------------------------


class TestNamedQueryCreate:
    def test_valid_minimal(self) -> None:
        data = NamedQueryCreate(
            name="my-query",
            query_params=EPCISQueryParams(),
        )
        assert data.name == "my-query"
        assert data.description is None
        assert data.query_params.limit == 100

    def test_valid_with_description_and_filters(self) -> None:
        data = NamedQueryCreate(
            name="commissioning-events",
            description="All commissioning events for battery DPPs",
            query_params=EPCISQueryParams(
                eq_biz_step="commissioning",
                eq_action="ADD",
                limit=50,
            ),
        )
        assert data.description == "All commissioning events for battery DPPs"
        assert data.query_params.eq_biz_step == "commissioning"
        assert data.query_params.limit == 50

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            NamedQueryCreate(
                name="",
                query_params=EPCISQueryParams(),
            )

    def test_name_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError, match="String should have at most 255 characters"):
            NamedQueryCreate(
                name="x" * 256,
                query_params=EPCISQueryParams(),
            )

    def test_max_length_name_accepted(self) -> None:
        data = NamedQueryCreate(
            name="x" * 255,
            query_params=EPCISQueryParams(),
        )
        assert len(data.name) == 255

    def test_query_params_serialization(self) -> None:
        params = EPCISQueryParams(
            eq_biz_step="shipping",
            dpp_id=uuid4(),
            limit=200,
        )
        data = NamedQueryCreate(name="test", query_params=params)
        dumped = data.query_params.model_dump(mode="json", exclude_none=True)
        assert dumped["eq_biz_step"] == "shipping"
        assert dumped["limit"] == 200
        assert "dpp_id" in dumped


# ---------------------------------------------------------------------------
# NamedQueryResponse validation
# ---------------------------------------------------------------------------


class TestNamedQueryResponse:
    def test_from_attributes(self) -> None:
        now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=UTC)
        data = {
            "id": uuid4(),
            "name": "my-saved-query",
            "description": "A test query",
            "query_params": {"eq_biz_step": "commissioning", "limit": 100, "offset": 0},
            "created_by_subject": "user-abc",
            "created_at": now,
        }
        resp = NamedQueryResponse.model_validate(data)
        assert resp.name == "my-saved-query"
        assert resp.description == "A test query"
        assert resp.query_params["eq_biz_step"] == "commissioning"
        assert resp.created_by_subject == "user-abc"
        assert resp.created_at == now

    def test_description_defaults_to_none(self) -> None:
        data = {
            "id": uuid4(),
            "name": "no-desc",
            "query_params": {"limit": 100, "offset": 0},
            "created_by_subject": "user-xyz",
            "created_at": datetime(2026, 2, 8, tzinfo=UTC),
        }
        resp = NamedQueryResponse.model_validate(data)
        assert resp.description is None

    def test_query_params_is_dict(self) -> None:
        """query_params in the response is a raw dict (not EPCISQueryParams)."""
        data = {
            "id": uuid4(),
            "name": "raw-params",
            "query_params": {"eq_action": "ADD", "limit": 50},
            "created_by_subject": "user-123",
            "created_at": datetime(2026, 2, 8, tzinfo=UTC),
        }
        resp = NamedQueryResponse.model_validate(data)
        assert isinstance(resp.query_params, dict)
        assert resp.query_params["eq_action"] == "ADD"


# ---------------------------------------------------------------------------
# Round-trip: create → serialize → deserialize for execution
# ---------------------------------------------------------------------------


class TestNamedQueryRoundtrip:
    def test_params_roundtrip_via_json(self) -> None:
        """Params dumped from NamedQueryCreate can be re-parsed as EPCISQueryParams."""
        create = NamedQueryCreate(
            name="roundtrip-test",
            query_params=EPCISQueryParams(
                eq_biz_step="receiving",
                eq_disposition="in_progress",
                limit=500,
                offset=10,
            ),
        )
        # Simulate what the service does: dump to dict for JSONB storage
        stored = create.query_params.model_dump(mode="json", exclude_none=True)
        # Simulate what execute_named_query does: re-parse stored params
        restored = EPCISQueryParams.model_validate(stored)
        assert restored.eq_biz_step == "receiving"
        assert restored.eq_disposition == "in_progress"
        assert restored.limit == 500
        assert restored.offset == 10
