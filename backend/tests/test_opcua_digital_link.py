"""Tests for the /digital-link endpoint."""

from __future__ import annotations


def test_build_digital_link_uri():
    from app.modules.dpps.router import _build_digital_link_uri

    uri = _build_digital_link_uri(
        resolver_base_url="https://id.example.com",
        gtin="4006381333931",
        serial="SN-001",
    )
    assert uri == "https://id.example.com/01/4006381333931/21/SN-001"


def test_build_digital_link_uri_no_serial():
    from app.modules.dpps.router import _build_digital_link_uri

    uri = _build_digital_link_uri(
        resolver_base_url="https://id.example.com",
        gtin="4006381333931",
    )
    assert uri == "https://id.example.com/01/4006381333931"
