"""Tests for data carrier publish gate enforcement."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db.models import (
    DataCarrierIdentifierScheme,
    DataCarrierIdentityLevel,
    DataCarrierStatus,
    DataCarrierType,
)
from app.modules.data_carriers.profile import DataCarrierComplianceProfile
from app.modules.dpps.service import DPPService


def _carrier(
    *,
    status: DataCarrierStatus = DataCarrierStatus.ACTIVE,
    carrier_type: DataCarrierType = DataCarrierType.QR,
    identity_level: DataCarrierIdentityLevel = DataCarrierIdentityLevel.ITEM,
    identifier_scheme: DataCarrierIdentifierScheme = DataCarrierIdentifierScheme.GS1_GTIN,
    is_gtin_verified: bool = True,
    pre_sale_enabled: bool = True,
) -> MagicMock:
    item = MagicMock()
    item.status = status
    item.carrier_type = carrier_type
    item.identity_level = identity_level
    item.identifier_scheme = identifier_scheme
    item.is_gtin_verified = is_gtin_verified
    item.pre_sale_enabled = pre_sale_enabled
    return item


@pytest.mark.asyncio
async def test_gate_blocks_when_enabled_and_no_carriers() -> None:
    session = AsyncMock()
    service = DPPService(session)
    dpp_id = uuid4()
    tenant_id = uuid4()

    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    with patch.object(
        service,
        "_load_data_carrier_publish_gate",
        AsyncMock(return_value=(True, DataCarrierComplianceProfile())),
    ), pytest.raises(ValueError, match="requires at least one managed carrier"):
        await service._assert_data_carrier_publish_gate(dpp_id=dpp_id, tenant_id=tenant_id)


@pytest.mark.asyncio
async def test_gate_passes_when_matching_active_carrier_exists() -> None:
    session = AsyncMock()
    service = DPPService(session)
    dpp_id = uuid4()
    tenant_id = uuid4()

    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _carrier(
            status=DataCarrierStatus.ACTIVE,
            carrier_type=DataCarrierType.QR,
            identity_level=DataCarrierIdentityLevel.ITEM,
            identifier_scheme=DataCarrierIdentifierScheme.GS1_GTIN,
            is_gtin_verified=True,
        )
    ]
    session.execute = AsyncMock(return_value=result)

    with patch.object(
        service,
        "_load_data_carrier_publish_gate",
        AsyncMock(return_value=(True, DataCarrierComplianceProfile())),
    ):
        await service._assert_data_carrier_publish_gate(dpp_id=dpp_id, tenant_id=tenant_id)


@pytest.mark.asyncio
async def test_gate_blocks_when_only_withdrawn_carriers_exist() -> None:
    session = AsyncMock()
    service = DPPService(session)
    dpp_id = uuid4()
    tenant_id = uuid4()

    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        _carrier(status=DataCarrierStatus.WITHDRAWN),
        _carrier(status=DataCarrierStatus.DEPRECATED),
    ]
    session.execute = AsyncMock(return_value=result)

    with patch.object(
        service,
        "_load_data_carrier_publish_gate",
        AsyncMock(return_value=(True, DataCarrierComplianceProfile())),
    ), pytest.raises(ValueError, match="no data carrier satisfies"):
        await service._assert_data_carrier_publish_gate(dpp_id=dpp_id, tenant_id=tenant_id)

