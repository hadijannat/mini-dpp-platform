"""
Unit tests for ABAC enforcement behavior.
"""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.security import abac as abac_module
from app.core.security.abac import PolicyDecision, PolicyEffect, check_access, require_access
from app.core.security.oidc import TokenPayload


def _mock_user() -> TokenPayload:
    return TokenPayload(
        sub="test-user",
        email="test@example.com",
        preferred_username="test",
        roles=["publisher"],
        bpn=None,
        org=None,
        clearance="public",
        exp=datetime.now(UTC),
        iat=datetime.now(UTC),
        raw_claims={},
    )


@pytest.mark.asyncio
async def test_check_access_allows_when_opa_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPA_ENABLED", "false")
    get_settings.cache_clear()

    decision = await check_access(_mock_user(), "read", {"type": "dpp"})

    assert decision.effect == PolicyEffect.ALLOW
    assert decision.policy_id == "opa-disabled"


@pytest.mark.asyncio
async def test_require_access_denies_when_opa_returns_deny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPA_ENABLED", "true")
    get_settings.cache_clear()

    async def _deny(_context):
        return PolicyDecision(effect=PolicyEffect.DENY, reason="denied")

    monkeypatch.setattr(abac_module._opa_client, "evaluate", _deny)

    with pytest.raises(HTTPException) as exc:
        await require_access(_mock_user(), "read", {"type": "dpp"})

    assert exc.value.status_code == 403
