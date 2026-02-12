"""Utilities for identifying plaintext secrets in connector payloads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

SENSITIVE_KEYWORDS = ("secret", "token", "password", "api_key", "apikey")
SAFE_KEY_SUFFIXES = ("_secret_ref", "secret_ref")
ENCRYPTED_PREFIX = "enc:v1:"


@dataclass(slots=True)
class PlaintextSecretFinding:
    """A plaintext secret candidate discovered inside a payload."""

    path: str
    key: str
    value_preview: str


def is_encrypted_secret_value(value: Any) -> bool:
    """Return True when a value matches the encrypted payload prefix."""
    return isinstance(value, str) and value.startswith(ENCRYPTED_PREFIX)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    if lowered.endswith(SAFE_KEY_SUFFIXES):
        return False
    return any(keyword in lowered for keyword in SENSITIVE_KEYWORDS)


def _preview(value: str, *, max_chars: int = 12) -> str:
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}..."


def find_plaintext_secret_fields(payload: Mapping[str, Any]) -> list[PlaintextSecretFinding]:
    """Scan a mapping recursively and report plaintext values under sensitive keys."""
    findings: list[PlaintextSecretFinding] = []

    def _walk(node: Any, *, path: str) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                key_str = str(key)
                next_path = f"{path}.{key_str}" if path else key_str
                if (
                    _is_sensitive_key(key_str)
                    and isinstance(value, str)
                    and value.strip()
                    and not is_encrypted_secret_value(value)
                ):
                    findings.append(
                        PlaintextSecretFinding(
                            path=next_path,
                            key=key_str,
                            value_preview=_preview(value),
                        )
                    )
                _walk(value, path=next_path)
            return

        if isinstance(node, list):
            for index, value in enumerate(node):
                _walk(value, path=f"{path}[{index}]")

    _walk(payload, path="")
    return findings
