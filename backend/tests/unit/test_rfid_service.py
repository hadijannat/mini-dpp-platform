"""Unit tests for RFID service response mapping helpers."""

from unittest.mock import AsyncMock

import pytest

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
