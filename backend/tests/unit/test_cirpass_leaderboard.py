"""Unit tests for CIRPASS public session + leaderboard rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import jwt
import pytest

import app.modules.cirpass.service as cirpass_service_module
from app.db.models import CirpassLeaderboardEntry
from app.modules.cirpass.schemas import CirpassLeaderboardSubmitRequest
from app.modules.cirpass.service import (
    CirpassLabService,
    CirpassRateLimitError,
    CirpassSessionError,
    CirpassValidationError,
)


class _FakeScalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


@dataclass
class _FakeScalarResult:
    rows: list[Any]

    def scalar_one_or_none(self) -> Any:
        return self.rows[0] if self.rows else None

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self.rows)


class _FakeSession:
    def __init__(self) -> None:
        self.entries: list[CirpassLeaderboardEntry] = []

    async def execute(self, statement: object) -> _FakeScalarResult:
        sql = str(statement)
        params = statement.compile().params  # type: ignore[attr-defined]

        if "DELETE FROM cirpass_leaderboard_entries" in sql:
            cutoff = params.get("created_at_1")
            if cutoff is not None:
                self.entries = [entry for entry in self.entries if entry.created_at >= cutoff]
            return _FakeScalarResult([])

        if "FROM cirpass_leaderboard_entries" not in sql:
            return _FakeScalarResult([])

        if "WHERE cirpass_leaderboard_entries.sid" in sql and "version" in sql and "ORDER BY" not in sql:
            sid = params.get("sid_1")
            version = params.get("version_1")
            for entry in self.entries:
                if entry.sid == sid and entry.version == version:
                    return _FakeScalarResult([entry])
            return _FakeScalarResult([])

        if "WHERE cirpass_leaderboard_entries.version" in sql:
            version = params.get("version_1")
            ranked = sorted(
                [entry for entry in self.entries if entry.version == version],
                key=lambda item: (-item.score, item.completion_seconds, item.created_at),
            )
            return _FakeScalarResult(ranked)

        return _FakeScalarResult([])

    def add(self, entry: CirpassLeaderboardEntry) -> None:
        if entry.created_at is None:
            entry.created_at = datetime.now(UTC)
        if entry.updated_at is None:
            entry.updated_at = entry.created_at
        self.entries.append(entry)

    async def flush(self) -> None:
        return None


def _payload(token: str, nickname: str = "builder_01", score: int = 420) -> CirpassLeaderboardSubmitRequest:
    return CirpassLeaderboardSubmitRequest(
        session_token=token,
        nickname=nickname,
        score=score,
        completion_seconds=300,
        version="V3.1",
    )


@pytest.mark.asyncio
async def test_submit_rejects_tampered_and_expired_tokens() -> None:
    cirpass_service_module._sid_event_window.clear()
    cirpass_service_module._ip_event_window.clear()

    service = CirpassLabService(_FakeSession())  # type: ignore[arg-type]
    session = await service.create_session(user_agent="UnitTestAgent")

    with pytest.raises(CirpassSessionError):
        await service.submit_score(
            payload=_payload(f"{session.session_token}x"),
            user_agent="UnitTestAgent",
            client_ip="10.0.0.1",
        )

    expired_token = jwt.encode(
        {
            "sid": "expired-sid",
            "iat": int(datetime(2024, 1, 1, tzinfo=UTC).timestamp()),
            "exp": int(datetime(2024, 1, 1, tzinfo=UTC).timestamp()),
            "ua_hash": service._hash_user_agent("UnitTestAgent"),  # noqa: SLF001
        },
        service.settings.cirpass_session_token_secret,
        algorithm="HS256",
    )

    with pytest.raises(CirpassSessionError):
        await service.submit_score(
            payload=_payload(expired_token),
            user_agent="UnitTestAgent",
            client_ip="10.0.0.1",
        )


@pytest.mark.asyncio
async def test_submit_validates_nickname_pattern() -> None:
    cirpass_service_module._sid_event_window.clear()
    cirpass_service_module._ip_event_window.clear()

    service = CirpassLabService(_FakeSession())  # type: ignore[arg-type]
    session = await service.create_session(user_agent="UnitTestAgent")

    with pytest.raises(CirpassValidationError):
        await service.submit_score(
            payload=_payload(session.session_token, nickname="bad nickname!"),
            user_agent="UnitTestAgent",
            client_ip="10.0.0.2",
        )


@pytest.mark.asyncio
async def test_leaderboard_keeps_best_score_and_enforces_sid_limit() -> None:
    cirpass_service_module._sid_event_window.clear()
    cirpass_service_module._ip_event_window.clear()

    fake_db = _FakeSession()
    service = CirpassLabService(fake_db)  # type: ignore[arg-type]
    session = await service.create_session(user_agent="UnitTestAgent")

    first = await service.submit_score(
        payload=_payload(session.session_token, score=300),
        user_agent="UnitTestAgent",
        client_ip="10.0.0.3",
    )
    assert first.accepted is True

    second = await service.submit_score(
        payload=_payload(session.session_token, score=450),
        user_agent="UnitTestAgent",
        client_ip="10.0.0.3",
    )
    assert second.best_score == 450

    third = await service.submit_score(
        payload=_payload(session.session_token, score=410),
        user_agent="UnitTestAgent",
        client_ip="10.0.0.3",
    )
    assert third.accepted is True

    with pytest.raises(CirpassRateLimitError):
        await service.submit_score(
            payload=_payload(session.session_token, score=460),
            user_agent="UnitTestAgent",
            client_ip="10.0.0.3",
        )

    assert len(fake_db.entries) == 1
    assert fake_db.entries[0].score == 450

    leaderboard = await service.get_leaderboard(version="V3.1", limit=10)
    assert leaderboard.entries[0].score == 450
    assert leaderboard.entries[0].nickname == "builder_01"
