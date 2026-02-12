"""Unit tests for plaintext secret guardrail scanners."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.dataspace.secret_scan import (
    find_plaintext_secret_fields,
    is_encrypted_secret_value,
)
from tools.check_plaintext_connector_secrets import scan_plaintext_connector_secrets


def _scalars_result(values: list[object]) -> object:
    return SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: values),
    )


def test_is_encrypted_secret_value_recognizes_prefix() -> None:
    assert is_encrypted_secret_value("enc:v1:abc123")
    assert not is_encrypted_secret_value("plain-secret")
    assert not is_encrypted_secret_value(123)


def test_find_plaintext_secret_fields_detects_sensitive_keys() -> None:
    payload = {
        "token": "plain-token",
        "management_api_key_secret_ref": "edc-key-ref",
        "nested": [{"api_key": "plain-api-key"}],
    }
    findings = find_plaintext_secret_fields(payload)

    paths = {finding.path for finding in findings}
    assert "token" in paths
    assert "nested[0].api_key" in paths
    assert all(finding.path != "management_api_key_secret_ref" for finding in findings)


@pytest.mark.asyncio
async def test_scan_plaintext_connector_secrets_collects_all_scopes() -> None:
    tenant_id = uuid4()
    connector_id = uuid4()

    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalars_result(
                [
                    SimpleNamespace(
                        id=connector_id,
                        tenant_id=tenant_id,
                        name="legacy-one",
                        config={"token": "legacy-plain-token"},
                    )
                ]
            ),
            _scalars_result(
                [
                    SimpleNamespace(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        name="dataspace-one",
                        runtime=SimpleNamespace(value="catena_x_dtr"),
                        runtime_config={"client_secret": "plain-runtime-secret"},
                    )
                ]
            ),
            _scalars_result(
                [
                    SimpleNamespace(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        connector_id=connector_id,
                        secret_ref="ok-secret",
                        encrypted_value="enc:v1:abc",
                    ),
                    SimpleNamespace(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        connector_id=connector_id,
                        secret_ref="bad-secret",
                        encrypted_value="plaintext-secret",
                    ),
                ]
            ),
        ]
    )

    findings = await scan_plaintext_connector_secrets(session)

    scopes = [finding["scope"] for finding in findings]
    assert "legacy_connector_config" in scopes
    assert "dataspace_runtime_config" in scopes
    assert "dataspace_connector_secret" in scopes
