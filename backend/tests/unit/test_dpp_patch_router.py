from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.db.models import DPPStatus
from app.modules.dpps.router import PatchSubmodelRequest, patch_submodel


def _publisher_tenant(*, subject: str = "publisher-sub", is_tenant_admin: bool = False):
    return SimpleNamespace(
        tenant_id=uuid4(),
        tenant_slug="default",
        user=SimpleNamespace(sub=subject),
        is_tenant_admin=is_tenant_admin,
    )


@pytest.mark.asyncio()
async def test_patch_submodel_endpoint_forwards_operations_to_service() -> None:
    tenant = _publisher_tenant(subject="owner-user")
    dpp_id = uuid4()
    revision_id = uuid4()

    service = SimpleNamespace(
        get_dpp=AsyncMock(
            return_value=SimpleNamespace(
                id=dpp_id,
                owner_subject="owner-user",
                status=DPPStatus.DRAFT,
            )
        ),
        patch_submodel=AsyncMock(
            return_value=SimpleNamespace(
                id=revision_id,
                revision_no=4,
                state=SimpleNamespace(value="draft"),
                digest_sha256="digest-123",
                created_by_subject="owner-user",
                created_at=SimpleNamespace(isoformat=lambda: "2026-02-13T12:00:00+00:00"),
                template_provenance={"digital-nameplate": {"version": "3.0.1"}},
            )
        ),
    )

    body = PatchSubmodelRequest(
        template_key="digital-nameplate",
        operations=[
            {
                "op": "set_value",
                "path": "ManufacturerName",
                "value": "New",
            }
        ],
        strict=True,
    )

    with (
        patch("app.modules.dpps.router.DPPService", return_value=service),
        patch("app.modules.dpps.router.require_access", new=AsyncMock()) as require_access,
        patch("app.modules.dpps.router.emit_audit_event", new=AsyncMock()) as emit_audit,
    ):
        response = await patch_submodel(
            dpp_id=dpp_id,
            body=body,
            request=SimpleNamespace(),
            db=AsyncMock(),
            tenant=tenant,
        )

    require_access.assert_awaited_once()
    service.patch_submodel.assert_awaited_once()
    emit_audit.assert_awaited_once()
    assert response.id == revision_id
    assert response.revision_no == 4


@pytest.mark.asyncio()
async def test_patch_submodel_endpoint_forbidden_for_non_owner_non_admin() -> None:
    tenant = _publisher_tenant(subject="shared-user", is_tenant_admin=False)
    dpp_id = uuid4()
    service = SimpleNamespace(
        get_dpp=AsyncMock(
            return_value=SimpleNamespace(
                id=dpp_id,
                owner_subject="owner-user",
                status=DPPStatus.DRAFT,
            )
        )
    )
    body = PatchSubmodelRequest(template_key="digital-nameplate", operations=[])

    with (
        patch("app.modules.dpps.router.DPPService", return_value=service),
        pytest.raises(HTTPException) as exc_info,
    ):
        await patch_submodel(
            dpp_id=dpp_id,
            body=body,
            request=SimpleNamespace(),
            db=AsyncMock(),
            tenant=tenant,
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
