"""SMT qualifier parsing utilities.

Normalizes qualifier semantics into a stable representation that can drive
schema generation and UI hints.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

CARDINALITY_VALUES = {"One", "ZeroToOne", "ZeroToMany", "OneToMany"}

CARDINALITY_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/Cardinality/1/0",
    "https://admin-shell.io/SubmodelTemplates/Multiplicity/1/0",
}

EITHER_OR_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/EitherOr/1/0",
}

DEFAULT_VALUE_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/DefaultValue/1/0",
}

INITIAL_VALUE_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/InitialValue/1/0",
}

EXAMPLE_VALUE_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/ExampleValue/1/0",
}

ALLOWED_RANGE_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/AllowedRange/1/0",
}

ALLOWED_VALUE_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/AllowedValue/1/0",
}

REQUIRED_LANG_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/RequiredLang/1/0",
}

ACCESS_MODE_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/AccessMode/1/0",
}

FORM_TITLE_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/FormTitle/1/0",
}

FORM_INFO_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/FormInfo/1/0",
}

FORM_URL_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/FormUrl/1/0",
}

NAMING_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/Naming/1/0",
}

ALLOWED_ID_SHORT_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/AllowedIdShort/1/0",
}

EDIT_ID_SHORT_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/EditIdShort/1/0",
}

FORM_CHOICES_SEMANTIC_IDS = {
    "https://admin-shell.io/SubmodelTemplates/FormChoices/1/0",
}


@dataclass
class SmtQualifiers:
    cardinality: str | None = None
    either_or: str | None = None
    default_value: str | None = None
    initial_value: str | None = None
    example_value: str | None = None
    allowed_range: str | None = None
    allowed_value_regex: str | None = None
    required_lang: list[str] = field(default_factory=list)
    access_mode: str | None = None
    form_title: str | None = None
    form_info: str | None = None
    form_url: str | None = None
    form_choices: list[str] = field(default_factory=list)
    naming: str | None = None
    allowed_id_short: list[str] = field(default_factory=list)
    edit_id_short: bool | None = None


def parse_smt_qualifiers(qualifiers: Iterable[dict[str, Any]] | None) -> SmtQualifiers:
    result = SmtQualifiers()
    if not qualifiers:
        return result

    for qual in qualifiers:
        qtype = str(qual.get("type", "")).strip()
        semantic_id = _extract_semantic_id(qual)
        value = qual.get("value")

        if qtype in {"SMT/Cardinality", "Cardinality", "SMT/Multiplicity", "Multiplicity"} or (
            semantic_id in CARDINALITY_SEMANTIC_IDS
        ):
            if isinstance(value, str) and value in CARDINALITY_VALUES:
                result.cardinality = value
            elif value is not None:
                result.cardinality = str(value)
            continue

        if qtype in {"SMT/EitherOr", "EitherOr"} or semantic_id in EITHER_OR_SEMANTIC_IDS:
            result.either_or = _string_value(value)
            continue

        if (
            qtype in {"SMT/DefaultValue", "DefaultValue"}
            or semantic_id in DEFAULT_VALUE_SEMANTIC_IDS
        ):
            result.default_value = _string_value(value)
            continue

        if (
            qtype in {"SMT/InitialValue", "InitialValue"}
            or semantic_id in INITIAL_VALUE_SEMANTIC_IDS
        ):
            result.initial_value = _string_value(value)
            continue

        if (
            qtype in {"SMT/ExampleValue", "ExampleValue"}
            or semantic_id in EXAMPLE_VALUE_SEMANTIC_IDS
        ):
            result.example_value = _string_value(value)
            continue

        if (
            qtype in {"SMT/AllowedRange", "AllowedRange"}
            or semantic_id in ALLOWED_RANGE_SEMANTIC_IDS
        ):
            result.allowed_range = _string_value(value)
            continue

        if (
            qtype in {"SMT/AllowedValue", "AllowedValue"}
            or semantic_id in ALLOWED_VALUE_SEMANTIC_IDS
        ):
            result.allowed_value_regex = _string_value(value)
            continue

        if (
            qtype in {"SMT/RequiredLang", "RequiredLang"}
            or semantic_id in REQUIRED_LANG_SEMANTIC_IDS
        ):
            result.required_lang.extend(_split_langs(value))
            continue

        if qtype in {"SMT/AccessMode", "AccessMode"} or semantic_id in ACCESS_MODE_SEMANTIC_IDS:
            result.access_mode = _string_value(value)
            continue

        if qtype in {"SMT/FormTitle", "FormTitle"} or semantic_id in FORM_TITLE_SEMANTIC_IDS:
            result.form_title = _string_value(value)
            continue

        if qtype in {"SMT/FormInfo", "FormInfo"} or semantic_id in FORM_INFO_SEMANTIC_IDS:
            result.form_info = _string_value(value)
            continue

        if qtype in {"SMT/FormUrl", "FormUrl"} or semantic_id in FORM_URL_SEMANTIC_IDS:
            result.form_url = _string_value(value)
            continue

        if qtype in {"SMT/FormChoices", "FormChoices"} or semantic_id in FORM_CHOICES_SEMANTIC_IDS:
            result.form_choices.extend(_split_choices(value))
            continue

        if qtype in {"SMT/Naming", "Naming"} or semantic_id in NAMING_SEMANTIC_IDS:
            result.naming = _string_value(value)
            continue

        if (
            qtype in {"SMT/AllowedIdShort", "AllowedIdShort"}
            or semantic_id in ALLOWED_ID_SHORT_SEMANTIC_IDS
        ):
            result.allowed_id_short.extend(_split_choices(value))
            continue

        if qtype in {"SMT/EditIdShort", "EditIdShort"} or semantic_id in EDIT_ID_SHORT_SEMANTIC_IDS:
            result.edit_id_short = _string_bool(value)
            continue

    return result


def parse_allowed_range(value: str | None) -> tuple[float, float] | None:
    if not value:
        return None
    match = re.match(
        r"^\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s*\.\.\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s*$", value
    )
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


def _split_langs(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(lang).strip() for lang in value if str(lang).strip()]
    if isinstance(value, str):
        tokens = re.split(r"[;,\s]+", value)
        return [token.strip() for token in tokens if token.strip()]
    return [str(value).strip()] if str(value).strip() else []


def _split_choices(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(choice).strip() for choice in value if str(choice).strip()]
    if isinstance(value, str):
        tokens = re.split(r"[;,\n]+", value)
        return [token.strip() for token in tokens if token.strip()]
    return [str(value).strip()] if str(value).strip() else []


def _string_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _string_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def _extract_semantic_id(qualifier: dict[str, Any]) -> str | None:
    semantic_id = qualifier.get("semanticId") or qualifier.get("semanticID")
    if isinstance(semantic_id, dict):
        keys = semantic_id.get("keys", [])
        if isinstance(keys, list) and keys:
            key_value = keys[0].get("value")
            if key_value:
                return str(key_value)
    return None
