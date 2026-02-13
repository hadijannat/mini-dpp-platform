"""Deterministic idShort generation helpers for repeatable SMT list items."""

from __future__ import annotations

import re
from collections.abc import Iterable

_PLACEHOLDER_RE = re.compile(r"\{(0+)\}")


def generate_next_id_short(template_id_short: str, existing_id_shorts: Iterable[str]) -> str:
    """Generate the next deterministic idShort.

    Preferred strategy follows SMT placeholder patterns such as ``Material{00}``.
    If no placeholder exists, fall back to ``<templateIdShort>_<n>``.
    """
    existing = {item for item in existing_id_shorts if item}
    match = _PLACEHOLDER_RE.search(template_id_short)
    if match:
        zeros = match.group(1)
        width = len(zeros)
        prefix = template_id_short[: match.start()]
        suffix = template_id_short[match.end() :]
        used: set[int] = set()
        placeholder_pattern = re.compile(
            rf"^{re.escape(prefix)}(\d{{{width}}}){re.escape(suffix)}$"
        )
        for candidate in existing:
            candidate_match = placeholder_pattern.match(candidate)
            if candidate_match:
                used.add(int(candidate_match.group(1)))
        index = 1
        while index in used:
            index += 1
        value = str(index).zfill(width)
        return f"{prefix}{value}{suffix}"

    index = 1
    while f"{template_id_short}_{index}" in existing:
        index += 1
    return f"{template_id_short}_{index}"


def validate_id_short_policy(
    *,
    candidate: str,
    allowed_id_shorts: list[str] | None = None,
    naming_regex: str | None = None,
) -> None:
    """Validate a generated or user-supplied idShort against SMT policy."""
    if allowed_id_shorts and candidate not in set(allowed_id_shorts):
        allowed = ", ".join(allowed_id_shorts)
        raise ValueError(f"idShort '{candidate}' is not allowed. Allowed values: {allowed}")

    if naming_regex:
        try:
            pattern = re.compile(naming_regex)
        except re.error as exc:
            raise ValueError(f"Invalid SMT/Naming regex: {naming_regex}") from exc
        if pattern.fullmatch(candidate) is None:
            raise ValueError(
                f"idShort '{candidate}' does not satisfy SMT/Naming regex '{naming_regex}'"
            )
