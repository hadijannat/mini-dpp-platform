from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.db.models import DPPStatus
from app.modules.dpps.service import AmbiguousSubmodelBindingError, DPPService


@pytest.mark.asyncio()
async def test_update_submodel_requires_submodel_id_when_template_binding_is_ambiguous() -> None:
    service = DPPService.__new__(DPPService)
    service._session = SimpleNamespace(add=MagicMock(), flush=AsyncMock())
    service._is_legacy_environment = MagicMock(return_value=False)
    service._calculate_digest = MagicMock(return_value="digest")
    service._cleanup_old_draft_revisions = AsyncMock(return_value=0)
    service._assert_conformant_environment = MagicMock(return_value=None)

    current_revision = SimpleNamespace(
        revision_no=2,
        aas_env_json={
            "assetAdministrationShells": [],
            "conceptDescriptions": [],
            "submodels": [
                {
                    "id": "urn:dpp:sm:1",
                    "idShort": "CarbonFootprintA",
                    "semanticId": {
                        "keys": [
                            {
                                "type": "GlobalReference",
                                "value": "https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0",
                            }
                        ]
                    },
                },
                {
                    "id": "urn:dpp:sm:2",
                    "idShort": "CarbonFootprintB",
                    "semanticId": {
                        "keys": [
                            {
                                "type": "GlobalReference",
                                "value": "https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0",
                            }
                        ]
                    },
                },
            ],
        },
        template_provenance={},
    )
    service.get_latest_revision = AsyncMock(return_value=current_revision)
    service.get_dpp = AsyncMock(
        return_value=SimpleNamespace(
            status=DPPStatus.DRAFT,
            asset_ids={"manufacturerPartId": "P-100"},
        )
    )
    service._template_service = SimpleNamespace(
        get_template=AsyncMock(return_value=SimpleNamespace(template_key="carbon-footprint")),
        get_all_templates=AsyncMock(
            return_value=[
                SimpleNamespace(
                    template_key="carbon-footprint",
                    semantic_id="https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0",
                )
            ]
        ),
    )
    service._basyx_builder = SimpleNamespace(update_submodel_environment=MagicMock())

    with pytest.raises(AmbiguousSubmodelBindingError):
        await service.update_submodel(
            dpp_id=uuid4(),
            tenant_id=uuid4(),
            template_key="carbon-footprint",
            submodel_data={},
            updated_by_subject="publisher-sub",
        )

    service._basyx_builder.update_submodel_environment.assert_not_called()
