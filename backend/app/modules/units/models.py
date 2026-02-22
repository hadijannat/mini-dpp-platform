"""Typed models for UoM extraction, registry, and enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UomDataSpecification:
    preferred_name: dict[str, str]
    symbol: str
    specific_unit_id: str
    definition: dict[str, str]
    preferred_name_quantity: dict[str, str]
    quantity_id: str | None
    classification_system: str
    classification_system_version: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> UomDataSpecification | None:
        symbol = str(payload.get("symbol") or payload.get("unitSymbol") or "").strip()
        specific_unit_id = str(payload.get("specificUnitID") or "").strip()
        if not symbol or not specific_unit_id:
            return None

        preferred_name = _normalize_lang_map(payload.get("preferredName"))
        definition = _normalize_lang_map(payload.get("definition"))
        preferred_name_quantity = _normalize_lang_map(payload.get("preferredNameQuantity"))

        quantity_id_raw = str(payload.get("quantityID") or "").strip()
        classification_system = str(payload.get("classificationSystem") or "").strip()
        classification_system_version_raw = str(payload.get("classificationSystemVersion") or "").strip()

        return cls(
            preferred_name=preferred_name,
            symbol=symbol,
            specific_unit_id=specific_unit_id,
            definition=definition,
            preferred_name_quantity=preferred_name_quantity,
            quantity_id=quantity_id_raw or None,
            classification_system=classification_system,
            classification_system_version=classification_system_version_raw or None,
        )

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "preferredName": _lang_map_to_list(self.preferred_name),
            "symbol": self.symbol,
            "specificUnitID": self.specific_unit_id,
            "definition": _lang_map_to_list(self.definition),
            "preferredNameQuantity": _lang_map_to_list(self.preferred_name_quantity),
            "classificationSystem": self.classification_system,
        }
        if self.quantity_id:
            payload["quantityID"] = self.quantity_id
        if self.classification_system_version:
            payload["classificationSystemVersion"] = self.classification_system_version
        return payload


@dataclass(frozen=True)
class UomRegistryEntry:
    cd_id: str
    data_specification: UomDataSpecification
    source: str = "seed"

    def to_payload(self) -> dict[str, Any]:
        return self.data_specification.to_payload()


def _normalize_lang_map(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, str):
        return {"en": value}
    if isinstance(value, dict):
        normalized: dict[str, str] = {}
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
            language = str(key).strip()
            text = str(item).strip()
            if language and text:
                normalized[language] = text
        return normalized
    if isinstance(value, list):
        normalized = {}
        for entry in value:
            if not isinstance(entry, dict):
                continue
            language = str(entry.get("language") or "").strip()
            text = str(entry.get("text") or "").strip()
            if language and text:
                normalized[language] = text
        return dict(sorted(normalized.items(), key=lambda pair: pair[0]))
    return {}


def _lang_map_to_list(value: dict[str, str]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for language, text in sorted(value.items(), key=lambda pair: pair[0]):
        language_normalized = str(language).strip()
        text_normalized = str(text).strip()
        if not language_normalized or not text_normalized:
            continue
        result.append({"language": language_normalized, "text": text_normalized})
    return result
