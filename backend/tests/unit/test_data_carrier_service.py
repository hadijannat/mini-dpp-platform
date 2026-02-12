"""Unit tests for data carrier service validation and identifier building."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.modules.data_carriers.schemas import (
    DataCarrierIdentifierData,
    DataCarrierIdentifierScheme,
    DataCarrierIdentityLevel,
    DataCarrierResolverStrategy,
)
from app.modules.data_carriers.service import DataCarrierError, DataCarrierService


@pytest.fixture()
def service() -> DataCarrierService:
    return DataCarrierService(AsyncMock())


class TestGS1IdentityValidation:
    def test_model_level_requires_gtin(self, service: DataCarrierService) -> None:
        with pytest.raises(DataCarrierError, match="GTIN is required"):
            service._build_gs1_identifier(
                identity_level=DataCarrierIdentityLevel.MODEL,
                identifier_data=DataCarrierIdentifierData(),
            )

    def test_batch_level_requires_batch(self, service: DataCarrierService) -> None:
        with pytest.raises(DataCarrierError, match="Batch is required"):
            service._build_gs1_identifier(
                identity_level=DataCarrierIdentityLevel.BATCH,
                identifier_data=DataCarrierIdentifierData(gtin="10614141000415"),
            )

    def test_item_level_requires_serial(self, service: DataCarrierService) -> None:
        with pytest.raises(DataCarrierError, match="Serial is required"):
            service._build_gs1_identifier(
                identity_level=DataCarrierIdentityLevel.ITEM,
                identifier_data=DataCarrierIdentifierData(gtin="10614141000415"),
            )

    def test_invalid_gtin_rejected(self, service: DataCarrierService) -> None:
        with pytest.raises(DataCarrierError, match="valid GS1 check digit"):
            service._build_gs1_identifier(
                identity_level=DataCarrierIdentityLevel.ITEM,
                identifier_data=DataCarrierIdentifierData(gtin="10614141000410", serial="SN1"),
            )

    def test_valid_item_level_identifier_builds_expected_key(self, service: DataCarrierService) -> None:
        key, uri, data, verified = service._build_gs1_identifier(
            identity_level=DataCarrierIdentityLevel.ITEM,
            identifier_data=DataCarrierIdentifierData(gtin="10614141000415", serial="SN1"),
        )
        assert key == "01/10614141000415/21/SN1"
        assert uri.endswith("/01/10614141000415/21/SN1")
        assert data["gtin"] == "10614141000415"
        assert data["serial"] == "SN1"
        assert verified is True

    def test_no_pseudo_gtin_fallback(self, service: DataCarrierService) -> None:
        with pytest.raises(DataCarrierError, match="GTIN is required"):
            service._build_gs1_identifier(
                identity_level=DataCarrierIdentityLevel.ITEM,
                identifier_data=DataCarrierIdentifierData(
                    manufacturer_part_id="PART-123",
                    serial="SER-1",
                ),
            )


class TestIdentifierRepresentation:
    def test_gs1_requires_dynamic_linkset(self, service: DataCarrierService) -> None:
        with pytest.raises(DataCarrierError, match="GS1 carriers require"):
            service._build_identifier_representation(
                dpp=AsyncMock(id="1", asset_ids={}),
                tenant_slug="default",
                identity_level=DataCarrierIdentityLevel.ITEM,
                identifier_scheme=DataCarrierIdentifierScheme.GS1_GTIN,
                resolver_strategy=DataCarrierResolverStrategy.DIRECT_PUBLIC_DPP,
                identifier_data=DataCarrierIdentifierData(gtin="10614141000415", serial="SN1"),
            )

    def test_direct_url_requires_http(self, service: DataCarrierService) -> None:
        with pytest.raises(DataCarrierError, match="direct_url must use http or https"):
            service._build_direct_url_identifier(
                DataCarrierIdentifierData.model_construct(direct_url="ftp://example.com"),
            )
