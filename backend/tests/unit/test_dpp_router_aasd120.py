"""Router contract tests for AASd-120 hardening paths."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.tenancy import TenantAdmin
from app.modules.dpps.router import (
    ImportDPPRequest,
    RepairInvalidListsRequest,
    import_dpp,
    repair_invalid_lists,
)


def _publisher_tenant() -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=uuid4(),
        tenant_slug="default",
        user=SimpleNamespace(sub="publisher-sub"),
        is_tenant_admin=False,
    )


def _tenant_admin() -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=uuid4(),
        tenant_slug="default",
        user=SimpleNamespace(sub="tenant-admin-sub"),
        is_tenant_admin=True,
    )


def _invalid_aasd120_environment() -> dict[str, object]:
    return {
        "assetAdministrationShells": [
            {
                "id": "urn:aas:1",
                "idShort": "AAS1",
                "modelType": "AssetAdministrationShell",
                "assetInformation": {
                    "assetKind": "Instance",
                    "globalAssetId": "urn:asset:1",
                },
                "submodels": [
                    {
                        "type": "ModelReference",
                        "keys": [{"type": "Submodel", "value": "urn:sm:1"}],
                    }
                ],
            }
        ],
        "submodels": [
            {
                "id": "urn:sm:1",
                "idShort": "SM1",
                "modelType": "Submodel",
                "submodelElements": [
                    {
                        "idShort": "PcfCalculationMethods",
                        "modelType": "SubmodelElementList",
                        "orderRelevant": True,
                        "typeValueListElement": "Property",
                        "valueTypeListElement": "xs:string",
                        "value": [
                            {
                                "idShort": "generated_submodel_list_hack_foo",
                                "modelType": "Property",
                                "valueType": "xs:string",
                                "value": "abc",
                            }
                        ],
                    }
                ],
            }
        ],
        "conceptDescriptions": [],
    }


class TestImportValidation:
    @pytest.mark.asyncio()
    async def test_import_rejects_invalid_submodel_list_item_id_short(self) -> None:
        db = AsyncMock()
        request = MagicMock()
        tenant = _publisher_tenant()
        body = ImportDPPRequest(root=_invalid_aasd120_environment())

        with (
            patch("app.modules.dpps.router.require_access", new=AsyncMock()),
            patch("app.modules.dpps.router.DPPService", return_value=MagicMock()),
            pytest.raises(HTTPException) as exc_info,
        ):
            await import_dpp(
                body=body,
                request=request,
                db=db,
                tenant=tenant,
            )

        assert exc_info.value.status_code == 422
        detail = exc_info.value.detail
        assert isinstance(detail, dict)
        assert "errors" in detail
        assert any("AASd-120" in error for error in detail["errors"])


class TestRepairInvalidListsRouter:
    def test_repair_endpoint_requires_tenant_admin_dependency(self) -> None:
        tenant_annotation = inspect.signature(repair_invalid_lists).parameters["tenant"].annotation
        assert tenant_annotation == TenantAdmin

    @pytest.mark.asyncio()
    async def test_repair_endpoint_returns_contract_shape(self) -> None:
        tenant = _tenant_admin()
        request = MagicMock()
        db = AsyncMock()

        service = SimpleNamespace(
            repair_invalid_list_item_id_shorts=AsyncMock(
                return_value={
                    "total": 2,
                    "repaired": 1,
                    "skipped": 1,
                    "errors": [{"dpp_id": uuid4(), "reason": "parse_failed:boom"}],
                    "dry_run": True,
                    "stats": {
                        "lists_scanned": 3,
                        "items_scanned": 4,
                        "idshort_removed": 1,
                        "paths_changed": 1,
                    },
                }
            )
        )

        with (
            patch("app.modules.dpps.router.DPPService", return_value=service),
            patch("app.modules.dpps.router.emit_audit_event", new=AsyncMock()) as emit_audit,
        ):
            response = await repair_invalid_lists(
                body=RepairInvalidListsRequest(dry_run=True, limit=50),
                request=request,
                db=db,
                tenant=tenant,
            )

        service.repair_invalid_list_item_id_shorts.assert_awaited_once_with(
            tenant_id=tenant.tenant_id,
            updated_by_subject=tenant.user.sub,
            dry_run=True,
            dpp_ids=None,
            limit=50,
        )
        db.commit.assert_awaited_once()
        emit_audit.assert_awaited_once()

        assert response.total == 2
        assert response.repaired == 1
        assert response.skipped == 1
        assert response.dry_run is True
        assert response.stats.lists_scanned == 3
        assert response.stats.idshort_removed == 1
        assert len(response.errors) == 1
