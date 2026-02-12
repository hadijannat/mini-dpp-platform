"""Unit tests for legacy connector service encryption wiring."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.db.models import Connector
from app.modules.connectors.catenax.service import CatenaXConnectorService


@pytest.fixture
def encryption_key_b64() -> str:
    return base64.b64encode(b"0123456789ABCDEF0123456789ABCDEF").decode("ascii")


@pytest.mark.asyncio
async def test_create_connector_encrypts_sensitive_fields(
    monkeypatch: pytest.MonkeyPatch,
    encryption_key_b64: str,
) -> None:
    monkeypatch.setenv("ENCRYPTION_MASTER_KEY", encryption_key_b64)
    get_settings.cache_clear()

    session = AsyncMock()
    session.flush = AsyncMock()
    added: list[object] = []

    def _add(entity: object) -> None:
        if isinstance(entity, Connector) and getattr(entity, "id", None) is None:
            entity.id = uuid4()
        added.append(entity)

    session.add = Mock(side_effect=_add)

    service = CatenaXConnectorService(session)
    connector = await service.create_connector(
        tenant_id=uuid4(),
        name="legacy-connector",
        config={
            "dtr_base_url": "https://dtr.example.com",
            "token": "plain-token",
            "client_secret": "plain-client-secret",
            "bpn": "BPNL000000000001",
        },
        created_by_subject="user-123",
    )

    assert connector.name == "legacy-connector"
    assert connector.config["token"].startswith("enc:v1:")
    assert connector.config["client_secret"].startswith("enc:v1:")
    assert connector.config["dtr_base_url"] == "https://dtr.example.com"

    decrypted = service._decrypt_config(connector.config)  # noqa: SLF001 - integration assertion
    assert decrypted["token"] == "plain-token"
    assert decrypted["client_secret"] == "plain-client-secret"

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_create_connector_requires_encryption_key_for_sensitive_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ENCRYPTION_MASTER_KEY", raising=False)
    get_settings.cache_clear()

    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = Mock()

    service = CatenaXConnectorService(session)
    with pytest.raises(ValueError, match="encryption_master_key"):
        await service.create_connector(
            tenant_id=uuid4(),
            name="legacy-connector",
            config={
                "dtr_base_url": "https://dtr.example.com",
                "token": "plain-token",
            },
            created_by_subject="user-123",
        )

    get_settings.cache_clear()
