from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.modules.dpps.router import import_dpp_aasx


class _UploadStub:
    def __init__(self, *, filename: str, chunks: list[bytes]) -> None:
        self.filename = filename
        self._chunks = chunks

    async def read(self, _size: int = -1) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


def _publisher_tenant() -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=uuid4(),
        tenant_slug="default",
        user=SimpleNamespace(sub="publisher-sub"),
        is_tenant_admin=False,
    )


@pytest.mark.asyncio()
async def test_import_aasx_rejects_payload_over_configured_limit() -> None:
    tenant = _publisher_tenant()
    file = _UploadStub(filename="payload.aasx", chunks=[b"abc", b"def"])

    with (
        patch("app.modules.dpps.router.require_access", new=AsyncMock()),
        patch(
            "app.modules.dpps.router.get_settings",
            return_value=SimpleNamespace(aasx_max_upload_bytes=5),
        ),
        patch("app.modules.dpps.router.AasxIngestService") as ingest_cls,
        pytest.raises(HTTPException) as exc_info,
    ):
        await import_dpp_aasx(
            request=MagicMock(),
            db=AsyncMock(),
            tenant=tenant,
            file=file,  # type: ignore[arg-type]
        )

    ingest_cls.assert_not_called()
    assert exc_info.value.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert "exceeds maximum upload size" in str(exc_info.value.detail)


@pytest.mark.asyncio()
async def test_import_aasx_sanitizes_parse_errors() -> None:
    tenant = _publisher_tenant()
    file = _UploadStub(filename="payload.aasx", chunks=[b"valid-ish", b""])
    ingest_service = SimpleNamespace(parse=MagicMock(side_effect=ValueError("boom /tmp/secret")))

    with (
        patch("app.modules.dpps.router.require_access", new=AsyncMock()),
        patch(
            "app.modules.dpps.router.get_settings",
            return_value=SimpleNamespace(aasx_max_upload_bytes=1024),
        ),
        patch("app.modules.dpps.router.AasxIngestService", return_value=ingest_service),
        pytest.raises(HTTPException) as exc_info,
    ):
        await import_dpp_aasx(
            request=MagicMock(),
            db=AsyncMock(),
            tenant=tenant,
            file=file,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert exc_info.value.detail == "Failed to parse AASX package"
