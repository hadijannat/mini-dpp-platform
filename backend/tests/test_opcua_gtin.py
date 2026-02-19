"""Tests for GTIN field on AssetIdsInput."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_asset_ids_accepts_valid_gtin():
    from app.modules.dpps.router import AssetIdsInput

    ids = AssetIdsInput(gtin="4006381333931")
    assert ids.gtin == "4006381333931"


def test_asset_ids_accepts_none_gtin():
    from app.modules.dpps.router import AssetIdsInput

    ids = AssetIdsInput()
    assert ids.gtin is None


def test_asset_ids_rejects_invalid_gtin():
    from app.modules.dpps.router import AssetIdsInput

    with pytest.raises(ValidationError, match="GTIN"):
        AssetIdsInput(gtin="1234567890123")
