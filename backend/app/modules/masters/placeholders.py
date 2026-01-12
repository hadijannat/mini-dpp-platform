"""Placeholder extraction and JSON pointer helpers for DPP master templates."""

from __future__ import annotations

import re
from typing import Any

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def extract_placeholder_paths(payload: Any) -> dict[str, list[str]]:
    """
    Extract placeholder names and their JSON Pointer paths.

    Returns a mapping of placeholder name -> sorted list of JSON Pointer paths.
    """
    paths: dict[str, set[str]] = {}

    def walk(value: Any, pointer: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                segment = _escape_pointer_segment(str(key))
                next_pointer = f"{pointer}/{segment}" if pointer else f"/{segment}"
                walk(child, next_pointer)
        elif isinstance(value, list):
            for idx, child in enumerate(value):
                next_pointer = f"{pointer}/{idx}" if pointer else f"/{idx}"
                walk(child, next_pointer)
        elif isinstance(value, str):
            for match in PLACEHOLDER_PATTERN.finditer(value):
                name = match.group(1)
                paths.setdefault(name, set()).add(pointer)

    walk(payload, "")

    return {name: sorted(pointer_set) for name, pointer_set in paths.items()}


def find_placeholders(payload: Any) -> set[str]:
    """Return a set of placeholder names found within the payload."""
    paths = extract_placeholder_paths(payload)
    return set(paths.keys())


def json_pointer_to_path(pointer: str) -> str:
    """Convert a JSON Pointer to a JSONPath-style string."""
    if not pointer:
        return "$"

    segments = pointer.lstrip("/").split("/")
    path = "$"
    for raw_segment in segments:
        segment = _unescape_pointer_segment(raw_segment)
        if _is_int(segment):
            path += f"[{segment}]"
        else:
            escaped = segment.replace("'", "\\'")
            path += f"['{escaped}']"
    return path


def resolve_json_pointer(payload: Any, pointer: str) -> Any:
    """Resolve a JSON Pointer against the payload. Returns None if not found."""
    if pointer == "":
        return payload

    segments = [_unescape_pointer_segment(seg) for seg in pointer.lstrip("/").split("/")]
    current: Any = payload

    for segment in segments:
        if isinstance(current, dict):
            if segment not in current:
                return None
            current = current[segment]
        elif isinstance(current, list):
            if not _is_int(segment):
                return None
            index = int(segment)
            if index < 0 or index >= len(current):
                return None
            current = current[index]
        else:
            return None

    return current


def set_json_pointer(payload: Any, pointer: str, value: Any) -> bool:
    """Set a JSON Pointer path on the payload. Returns False if path is invalid."""
    if pointer == "":
        return False

    segments = [_unescape_pointer_segment(seg) for seg in pointer.lstrip("/").split("/")]
    if not segments:
        return False

    current: Any = payload
    for segment in segments[:-1]:
        if isinstance(current, dict):
            if segment not in current:
                return False
            current = current[segment]
        elif isinstance(current, list):
            if not _is_int(segment):
                return False
            index = int(segment)
            if index < 0 or index >= len(current):
                return False
            current = current[index]
        else:
            return False

    last = segments[-1]
    if isinstance(current, dict):
        if last not in current:
            return False
        current[last] = value
        return True
    if isinstance(current, list):
        if not _is_int(last):
            return False
        index = int(last)
        if index < 0 or index >= len(current):
            return False
        current[index] = value
        return True

    return False


def _escape_pointer_segment(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def _unescape_pointer_segment(segment: str) -> str:
    return segment.replace("~1", "/").replace("~0", "~")


def _is_int(value: str) -> bool:
    return value.isdigit()
