"""Tests for the dataspace publication service."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import DataspacePublicationStatus


@pytest.mark.asyncio
async def test_create_publication_job():
    from app.modules.opcua.dataspace import DataspacePublicationService

    mock_session = MagicMock()
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
    from app.modules.opcua.dataspace import DataspacePublicationService

    mock_session = MagicMock()
    mock_job = MagicMock()
    mock_job.tenant_id = uuid.uuid4()
    mock_session.get = AsyncMock(return_value=mock_job)
    svc = DataspacePublicationService(mock_session)
    result = await svc.get_publication_job(uuid.uuid4(), mock_job.tenant_id)
    assert result is mock_job
