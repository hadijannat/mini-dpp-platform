"""Router contract tests for DPP attachment endpoints."""

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile, status

from app.db.models import DPPStatus
from app.modules.dpps.attachment_service import AttachmentNotFoundError
from app.modules.dpps.router import download_attachment, upload_attachment


def _publisher_tenant(*, subject: str = "publisher-sub", is_tenant_admin: bool = False):
    return SimpleNamespace(
        tenant_id=uuid4(),
        tenant_slug="default",
        user=SimpleNamespace(sub=subject),
        is_tenant_admin=is_tenant_admin,
    )


@pytest.mark.asyncio()
async def test_upload_attachment_forbidden_for_non_owner_non_admin() -> None:
    tenant = _publisher_tenant(subject="shared-user", is_tenant_admin=False)
    dpp_id = uuid4()

    service = SimpleNamespace(
        get_dpp=AsyncMock(
            return_value=SimpleNamespace(
                id=dpp_id, owner_subject="owner-user", status=DPPStatus.DRAFT
            )
        )
    )

    with (
        patch("app.modules.dpps.router.DPPService", return_value=service),
        pytest.raises(HTTPException) as exc_info,
    ):
        await upload_attachment(
            dpp_id=dpp_id,
            request=MagicMock(),
            db=AsyncMock(),
            tenant=tenant,
            file=UploadFile(filename="manual.pdf", file=io.BytesIO(b"data")),
            content_type="application/pdf",
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio()
async def test_upload_attachment_returns_private_url_and_commits() -> None:
    tenant = _publisher_tenant(subject="owner-user", is_tenant_admin=False)
    dpp_id = uuid4()
    attachment_id = uuid4()
    db = AsyncMock()

    service = SimpleNamespace(
        get_dpp=AsyncMock(
            return_value=SimpleNamespace(
                id=dpp_id, owner_subject="owner-user", status=DPPStatus.DRAFT
            )
        )
    )
    attachment_service = SimpleNamespace(
        upload_attachment=AsyncMock(
            return_value=SimpleNamespace(
                attachment_id=attachment_id,
                content_type="application/pdf",
                size_bytes=123,
            )
        )
    )

    with (
        patch("app.modules.dpps.router.DPPService", return_value=service),
        patch("app.modules.dpps.router.AttachmentService", return_value=attachment_service),
        patch("app.modules.dpps.router.require_access", new=AsyncMock()) as require_access,
        patch("app.modules.dpps.router.emit_audit_event", new=AsyncMock()) as emit_audit,
    ):
        response = await upload_attachment(
            dpp_id=dpp_id,
            request=MagicMock(),
            db=db,
            tenant=tenant,
            file=UploadFile(filename="manual.pdf", file=io.BytesIO(b"data")),
            content_type="application/pdf",
        )

    require_access.assert_awaited_once()
    attachment_service.upload_attachment.assert_awaited_once()
    db.commit.assert_awaited_once()
    emit_audit.assert_awaited_once()
    assert response.attachment_id == attachment_id
    assert response.url.endswith(f"/dpps/{dpp_id}/attachments/{attachment_id}")


@pytest.mark.asyncio()
async def test_download_attachment_allows_shared_reader_access() -> None:
    tenant = _publisher_tenant(subject="shared-user", is_tenant_admin=False)
    dpp_id = uuid4()
    attachment_id = uuid4()

    service = SimpleNamespace(
        get_dpp=AsyncMock(
            return_value=SimpleNamespace(
                id=dpp_id, owner_subject="owner-user", status=DPPStatus.DRAFT
            )
        ),
        is_resource_shared_with_user=AsyncMock(return_value=True),
    )
    attachment_service = SimpleNamespace(
        download_attachment_bytes=AsyncMock(
            return_value=(
                SimpleNamespace(filename="manual.pdf", content_type="application/pdf"),
                b"pdf-content",
            )
        )
    )

    with (
        patch("app.modules.dpps.router.DPPService", return_value=service),
        patch("app.modules.dpps.router.AttachmentService", return_value=attachment_service),
        patch("app.modules.dpps.router.require_access", new=AsyncMock()) as require_access,
        patch("app.modules.dpps.router.emit_audit_event", new=AsyncMock()) as emit_audit,
    ):
        response = await download_attachment(
            dpp_id=dpp_id,
            attachment_id=attachment_id,
            request=MagicMock(),
            db=AsyncMock(),
            tenant=tenant,
        )

    require_access.assert_awaited_once()
    emit_audit.assert_awaited_once()
    assert response.media_type == "application/pdf"
    assert "Content-Disposition" in response.headers


@pytest.mark.asyncio()
async def test_download_attachment_returns_404_when_missing() -> None:
    tenant = _publisher_tenant(subject="owner-user", is_tenant_admin=False)
    dpp_id = uuid4()
    attachment_id = uuid4()

    service = SimpleNamespace(
        get_dpp=AsyncMock(
            return_value=SimpleNamespace(
                id=dpp_id, owner_subject="owner-user", status=DPPStatus.DRAFT
            )
        ),
        is_resource_shared_with_user=AsyncMock(return_value=False),
    )
    attachment_service = SimpleNamespace(
        download_attachment_bytes=AsyncMock(
            side_effect=AttachmentNotFoundError("Attachment not found")
        )
    )

    with (
        patch("app.modules.dpps.router.DPPService", return_value=service),
        patch("app.modules.dpps.router.AttachmentService", return_value=attachment_service),
        patch("app.modules.dpps.router.require_access", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await download_attachment(
            dpp_id=dpp_id,
            attachment_id=attachment_id,
            request=MagicMock(),
            db=AsyncMock(),
            tenant=tenant,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
