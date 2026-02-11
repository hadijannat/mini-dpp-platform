"""MIME type validation helpers shared by DPP modules."""

from __future__ import annotations

import re
from functools import lru_cache

DEFAULT_MIME_REGEX = (
    r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}$"
)


@lru_cache(maxsize=32)
def _compiled_pattern(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def validate_mime_type(
    value: str | None,
    *,
    pattern: str = DEFAULT_MIME_REGEX,
    allow_empty: bool = False,
) -> str | None:
    """Validate MIME type syntax and return normalized value."""
    if value is None:
        return None if allow_empty else ""

    normalized = value.strip().lower()
    if not normalized:
        if allow_empty:
            return None
        return ""

    if not _compiled_pattern(pattern).fullmatch(normalized):
        raise ValueError(f"Invalid MIME type '{value}'")

    return normalized
