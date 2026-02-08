"""Unit tests for DPP revision diff algorithm."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.dpps.service import DPPService


class TestDiffJson:
    """Tests for the recursive JSON diff helper."""

    def _diff(
        self, old: Any, new: Any
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        return DPPService._diff_json(old, new)

    def test_identical_objects(self) -> None:
        obj = {"a": 1, "b": {"c": 2}}
        added, removed, changed = self._diff(obj, obj)
        assert added == []
        assert removed == []
        assert changed == []

    def test_added_keys(self) -> None:
        old: dict[str, Any] = {"a": 1}
        new = {"a": 1, "b": 2}
        added, removed, changed = self._diff(old, new)
        assert len(added) == 1
        assert added[0]["path"] == "b"
        assert added[0]["operation"] == "added"
        assert added[0]["new_value"] == 2
        assert removed == []
        assert changed == []

    def test_removed_keys(self) -> None:
        old = {"a": 1, "b": 2}
        new: dict[str, Any] = {"a": 1}
        added, removed, changed = self._diff(old, new)
        assert added == []
        assert len(removed) == 1
        assert removed[0]["path"] == "b"
        assert removed[0]["operation"] == "removed"
        assert removed[0]["old_value"] == 2
        assert changed == []

    def test_changed_string(self) -> None:
        old = {"name": "old"}
        new = {"name": "new"}
        added, removed, changed = self._diff(old, new)
        assert added == []
        assert removed == []
        assert len(changed) == 1
        assert changed[0]["path"] == "name"
        assert changed[0]["old_value"] == "old"
        assert changed[0]["new_value"] == "new"

    def test_changed_number(self) -> None:
        old = {"count": 1}
        new = {"count": 42}
        _, _, changed = self._diff(old, new)
        assert len(changed) == 1
        assert changed[0]["old_value"] == 1
        assert changed[0]["new_value"] == 42

    def test_changed_boolean(self) -> None:
        old = {"active": True}
        new = {"active": False}
        _, _, changed = self._diff(old, new)
        assert len(changed) == 1
        assert changed[0]["old_value"] is True
        assert changed[0]["new_value"] is False

    def test_nested_changes(self) -> None:
        old = {"outer": {"inner": "old_value"}}
        new = {"outer": {"inner": "new_value"}}
        _, _, changed = self._diff(old, new)
        assert len(changed) == 1
        assert changed[0]["path"] == "outer.inner"

    def test_deep_nested_addition(self) -> None:
        old: dict[str, Any] = {"a": {"b": {}}}
        new = {"a": {"b": {"c": "new"}}}
        added, _, _ = self._diff(old, new)
        assert len(added) == 1
        assert added[0]["path"] == "a.b.c"

    def test_array_change_detected(self) -> None:
        old = {"items": [1, 2, 3]}
        new = {"items": [1, 2, 4]}
        _, _, changed = self._diff(old, new)
        assert len(changed) == 1
        assert changed[0]["path"] == "items"
        assert changed[0]["old_value"] == [1, 2, 3]
        assert changed[0]["new_value"] == [1, 2, 4]

    def test_mixed_changes(self) -> None:
        old = {"keep": 1, "remove_me": "gone", "change_me": "old"}
        new = {"keep": 1, "add_me": "new", "change_me": "new"}
        added, removed, changed = self._diff(old, new)
        assert len(added) == 1
        assert added[0]["path"] == "add_me"
        assert len(removed) == 1
        assert removed[0]["path"] == "remove_me"
        assert len(changed) == 1
        assert changed[0]["path"] == "change_me"

    def test_empty_to_populated(self) -> None:
        old: dict[str, Any] = {}
        new = {"a": 1, "b": 2}
        added, _, _ = self._diff(old, new)
        assert len(added) == 2

    def test_populated_to_empty(self) -> None:
        old = {"a": 1, "b": 2}
        new: dict[str, Any] = {}
        _, removed, _ = self._diff(old, new)
        assert len(removed) == 2

    def test_type_change_dict_to_string(self) -> None:
        old = {"val": {"nested": 1}}
        new = {"val": "flat"}
        _, _, changed = self._diff(old, new)
        assert len(changed) == 1
        assert changed[0]["path"] == "val"
        assert changed[0]["old_value"] == {"nested": 1}
        assert changed[0]["new_value"] == "flat"

    def test_keys_sorted_in_output(self) -> None:
        old: dict[str, Any] = {}
        new = {"z": 1, "a": 2, "m": 3}
        added, _, _ = self._diff(old, new)
        paths = [e["path"] for e in added]
        assert paths == ["a", "m", "z"]


class TestDiffRevisions:
    """Tests for DPPService.diff_revisions method."""

    @pytest.fixture()
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture()
    def service(self, mock_session: AsyncMock) -> DPPService:
        svc = DPPService.__new__(DPPService)
        svc._session = mock_session
        return svc

    @pytest.mark.asyncio()
    async def test_diff_revisions_returns_result(self, service: DPPService) -> None:
        rev_a = MagicMock()
        rev_a.aas_env_json = {"key": "old"}
        rev_b = MagicMock()
        rev_b.aas_env_json = {"key": "new"}

        # Mock get_revision_by_no to return revisions in order
        service.get_revision_by_no = AsyncMock(side_effect=[rev_a, rev_b])  # type: ignore[method-assign]

        dpp_id = uuid4()
        tenant_id = uuid4()
        result = await service.diff_revisions(dpp_id, tenant_id, 1, 2)

        assert result["from_rev"] == 1
        assert result["to_rev"] == 2
        assert len(result["changed"]) == 1
        assert result["changed"][0]["path"] == "key"

    @pytest.mark.asyncio()
    async def test_diff_revisions_missing_rev_a(self, service: DPPService) -> None:
        service.get_revision_by_no = AsyncMock(return_value=None)  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="Revision 1 not found"):
            await service.diff_revisions(uuid4(), uuid4(), 1, 2)

    @pytest.mark.asyncio()
    async def test_diff_revisions_missing_rev_b(self, service: DPPService) -> None:
        rev_a = MagicMock()
        rev_a.aas_env_json = {}
        service.get_revision_by_no = AsyncMock(side_effect=[rev_a, None])  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="Revision 2 not found"):
            await service.diff_revisions(uuid4(), uuid4(), 1, 2)

    @pytest.mark.asyncio()
    async def test_diff_identical_revisions(self, service: DPPService) -> None:
        env = {"submodels": [{"idShort": "Nameplate"}]}
        rev_a = MagicMock()
        rev_a.aas_env_json = env
        rev_b = MagicMock()
        rev_b.aas_env_json = env

        service.get_revision_by_no = AsyncMock(side_effect=[rev_a, rev_b])  # type: ignore[method-assign]

        result = await service.diff_revisions(uuid4(), uuid4(), 1, 2)
        assert result["added"] == []
        assert result["removed"] == []
        assert result["changed"] == []
