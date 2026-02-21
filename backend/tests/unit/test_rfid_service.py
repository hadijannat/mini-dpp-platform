"""Unit tests for RFID service response mapping helpers."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.rfid.schemas import RFIDGS1Key, RFIDReadItem
from app.modules.rfid.service import RFIDService


def test_to_encode_response_uses_digital_link_for_missing_key_fields() -> None:
    payload = {
        "tdsScheme": "sgtin++",
        "tagLength": 96,
        "epcHex": "30340242201d8840009efdf7",
        "digitalLink": "https://acme.example.com/01/00037000302414/21/10419703",
        "fields": {},
    }
    response = RFIDService._to_encode_response(payload)
    assert response.gs1_key.gtin == "00037000302414"
    assert response.gs1_key.serial == "10419703"
    assert response.digital_link == "https://acme.example.com/01/00037000302414/21/10419703"


def test_to_decode_response_prefers_fields_when_present() -> None:
    payload = {
        "tdsScheme": "sgtin++",
        "tagLength": 96,
        "epcHex": "30340242201d8840009efdf7",
        "fields": {
            "gtin": "00037000302414",
            "serial": "10419703",
            "domain": "acme.example.com",
        },
    }
    response = RFIDService._to_decode_response(payload)
    assert response.gs1_key.gtin == "00037000302414"
    assert response.gs1_key.serial == "10419703"
    assert response.hostname == "acme.example.com"


@pytest.mark.asyncio
async def test_decode_fills_missing_digital_link_from_hostname() -> None:
    payload = {
        "tdsScheme": "sgtin++",
        "tagLength": 198,
        "epcHex": "36740242201d8858b068c5cb760cc00000000000000000000000",
        "fields": {
            "gtin": "00037000302414",
            "serial": "10419703",
            "domain": "acme.example.com",
        },
    }
    response = RFIDService._to_decode_response(payload)
    service = RFIDService(AsyncMock())
    hydrated = await service._ensure_digital_link(response, tenant_id=None)
    assert hydrated.digital_link == "https://acme.example.com/01/00037000302414/21/10419703"


@pytest.mark.asyncio
async def test_decode_read_for_ingest_uses_fallback_hostname() -> None:
    payload = {
        "tdsScheme": "sgtin++",
        "tagLength": 96,
        "epcHex": "30340242201d8840009efdf7",
        "fields": {
            "gtin": "00037000302414",
            "serial": "10419703",
        },
    }
    service = RFIDService(AsyncMock())
    service._client.decode = AsyncMock(return_value=payload)
    decoded = await service._decode_read_for_ingest(
        read=RFIDReadItem(epc_hex="30340242201d8840009efdf7"),
        fallback_hostname="acme.example.com",
    )
    assert decoded.digital_link == "https://acme.example.com/01/00037000302414/21/10419703"


@pytest.mark.asyncio
async def test_find_matching_dpp_id_uses_asset_ids_lookup_when_carrier_missing() -> None:
    carrier_result = MagicMock()
    carrier_result.scalar_one_or_none.return_value = None
    asset_result = MagicMock()
    expected_dpp_id = uuid4()
    asset_result.scalar_one_or_none.return_value = expected_dpp_id

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[carrier_result, asset_result])
    service = RFIDService(session)

    found = await service._find_matching_dpp_id(
        tenant_id=uuid4(),
        gs1_key=RFIDGS1Key(gtin="00037000302414", serial="10419703"),
    )
    assert found == expected_dpp_id
    assert session.execute.await_count == 2
