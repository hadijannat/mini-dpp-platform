"""
Unit tests for draft revision retention policy.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_cleanup_removes_old_drafts_beyond_limit() -> None:
    """Revisions beyond max_drafts limit should be deleted."""
    from app.modules.dpps.service import DPPService

    session = AsyncMock()
    service = DPPService(session)

    dpp_id = uuid4()
    tenant_id = uuid4()
    old_ids = [uuid4() for _ in range(5)]

    # Mock the select to return 5 old revision IDs
    select_result = MagicMock()
    select_result.scalars.return_value.all.return_value = old_ids

    # Mock the delete
    delete_result = MagicMock()

    session.execute = AsyncMock(side_effect=[select_result, delete_result])

    with patch.object(service, "_settings") as mock_settings:
        mock_settings.dpp_max_draft_revisions = 10
        count = await service._cleanup_old_draft_revisions(dpp_id, tenant_id)

    assert count == 5
    assert session.execute.call_count == 2


@pytest.mark.asyncio
async def test_cleanup_no_excess_does_nothing() -> None:
    """When drafts are within limit, no deletion occurs."""
    from app.modules.dpps.service import DPPService

    session = AsyncMock()
    service = DPPService(session)

    dpp_id = uuid4()
    tenant_id = uuid4()

    # Mock the select to return no old revision IDs
    select_result = MagicMock()
    select_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=select_result)

    with patch.object(service, "_settings") as mock_settings:
        mock_settings.dpp_max_draft_revisions = 10
        count = await service._cleanup_old_draft_revisions(dpp_id, tenant_id)

    assert count == 0
    # Only the select should have been called, no delete
    session.execute.assert_awaited_once()
