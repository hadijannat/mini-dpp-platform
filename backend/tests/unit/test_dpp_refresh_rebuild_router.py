from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.db.models import DPPStatus
from app.modules.dpps.router import refresh_rebuild_submodels


def _publisher_tenant(
    *, subject: str = "publisher-sub", is_tenant_admin: bool = False
) -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=uuid4(),
        tenant_slug="default",
        user=SimpleNamespace(sub=subject),
        is_tenant_admin=is_tenant_admin,
    )


@pytest.mark.asyncio()
async def test_refresh_rebuild_submodels_forbidden_for_non_owner_non_admin() -> None:
    dpp_id = uuid4()
    tenant = _publisher_tenant(subject="shared-sub", is_tenant_admin=False)
    db = AsyncMock()
    request = MagicMock()

    service = SimpleNamespace(
        get_dpp=AsyncMock(
            return_value=SimpleNamespace(owner_subject="owner-sub", status=DPPStatus.DRAFT)
        ),
        refresh_and_rebuild_dpp_submodels=AsyncMock(),
    )

    with (
        patch("app.modules.dpps.router.DPPService", return_value=service),
        pytest.raises(HTTPException) as exc_info,
    ):
        await refresh_rebuild_submodels(
            dpp_id=dpp_id,
            request=request,
            db=db,
            tenant=tenant,
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    service.refresh_and_rebuild_dpp_submodels.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio()
async def test_refresh_rebuild_submodels_returns_summary_and_audits() -> None:
    dpp_id = uuid4()
    tenant = _publisher_tenant(subject="owner-sub", is_tenant_admin=False)
    db = AsyncMock()
    db.get_bind = MagicMock(return_value=None)
    request = MagicMock()

    summary = {
        "attempted": 2,
        "succeeded": [
            {
                "template_key": "digital-nameplate",
                "submodel_id": "urn:sm:1",
                "submodel": "Nameplate",
            }
        ],
        "failed": [
            {
                "template_key": "carbon-footprint",
                "submodel_id": "urn:sm:2",
                "submodel": "CF",
                "error": "boom",
            }
        ],
        "skipped": [{"submodel": "Unknown", "reason": "no_matching_template"}],
    }
    service = SimpleNamespace(
        get_dpp=AsyncMock(
            return_value=SimpleNamespace(
                id=dpp_id,
                owner_subject=tenant.user.sub,
                status=DPPStatus.DRAFT,
            )
        ),
        refresh_and_rebuild_dpp_submodels=AsyncMock(return_value=summary),
    )

    with (
        patch("app.modules.dpps.router.DPPService", return_value=service),
        patch("app.modules.dpps.router.require_access", new=AsyncMock()) as require_access,
        patch("app.modules.dpps.router.emit_audit_event", new=AsyncMock()) as emit_audit,
    ):
        response = await refresh_rebuild_submodels(
            dpp_id=dpp_id,
            request=request,
            db=db,
            tenant=tenant,
        )

    require_access.assert_awaited_once()
    service.refresh_and_rebuild_dpp_submodels.assert_awaited_once_with(
        dpp_id=dpp_id,
        tenant_id=tenant.tenant_id,
        updated_by_subject=tenant.user.sub,
    )
    db.commit.assert_awaited_once()
    emit_audit.assert_awaited_once()
    assert response.attempted == 2
    assert len(response.succeeded) == 1
    assert len(response.failed) == 1
    assert len(response.skipped) == 1


@pytest.mark.asyncio()
async def test_refresh_rebuild_submodels_returns_conflict_when_lock_is_held() -> None:
    dpp_id = uuid4()
    tenant = _publisher_tenant(subject="owner-sub", is_tenant_admin=False)
    db = AsyncMock()
    request = MagicMock()

    service = SimpleNamespace(
        get_dpp=AsyncMock(
            return_value=SimpleNamespace(
                id=dpp_id,
                owner_subject=tenant.user.sub,
                status=DPPStatus.DRAFT,
            )
        ),
        refresh_and_rebuild_dpp_submodels=AsyncMock(),
    )

    @asynccontextmanager
    async def _lock_conflict(*_args: object, **_kwargs: object):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A refresh and rebuild is already in progress for this DPP",
        )
        yield

    with (
        patch("app.modules.dpps.router.DPPService", return_value=service),
        patch("app.modules.dpps.router.require_access", new=AsyncMock()),
        patch("app.modules.dpps.router._acquire_refresh_rebuild_guard", _lock_conflict),
        pytest.raises(HTTPException) as exc_info,
    ):
        await refresh_rebuild_submodels(
            dpp_id=dpp_id,
            request=request,
            db=db,
            tenant=tenant,
        )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    service.refresh_and_rebuild_dpp_submodels.assert_not_awaited()
    db.commit.assert_not_awaited()
