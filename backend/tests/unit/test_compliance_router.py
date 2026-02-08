"""Unit tests for the compliance router helpers."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.models import DPPStatus
from app.modules.compliance.router import _dpp_resource


class TestDppResource:
    """Tests for _dpp_resource() ABAC context builder.

    This helper must return a dict with type, id, owner_subject, and status.
    The status field was previously missing, causing OPA to default-deny
    all compliance check requests (PR #32).
    """

    def test_includes_status_from_enum(self) -> None:
        """Status field must be extracted from DPPStatus enum."""
        dpp_id = uuid4()
        dpp = SimpleNamespace(
            id=dpp_id,
            owner_subject="user-abc",
            status=DPPStatus.DRAFT,
        )
        result = _dpp_resource(dpp)
        assert result == {
            "type": "dpp",
            "id": str(dpp_id),
            "owner_subject": "user-abc",
            "status": "draft",
        }

    def test_includes_status_from_string(self) -> None:
        """Handles plain string status (no .value attribute)."""
        dpp_id = uuid4()
        dpp = SimpleNamespace(
            id=dpp_id,
            owner_subject="user-xyz",
            status="published",
        )
        result = _dpp_resource(dpp)
        assert result["status"] == "published"
        assert result["owner_subject"] == "user-xyz"
        assert len(result) == 4

    @pytest.mark.parametrize("member", list(DPPStatus))
    def test_all_statuses_produce_valid_context(self, member: DPPStatus) -> None:
        """Every DPPStatus enum member should produce a valid resource dict."""
        dpp = SimpleNamespace(id=uuid4(), owner_subject="u", status=member)
        result = _dpp_resource(dpp)
        assert set(result.keys()) == {"type", "id", "owner_subject", "status"}
        assert result["status"] == member.value
