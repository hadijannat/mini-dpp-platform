"""Submodel-to-template binding utilities.

Produces deterministic bindings for submodels in a DPP revision by combining:
- semantic IDs from submodels and template catalog entries
- legacy semantic ID aliases from the shared semantic registry
- template provenance captured on revisions
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.modules.semantic_registry import (
    get_template_support_status,
    is_template_refresh_enabled,
    load_semantic_registry,
)

BindingSource = Literal["semantic_exact", "semantic_alias", "provenance", "id_short", "unresolved"]


@dataclass(frozen=True)
class ResolvedSubmodelBinding:
    """Resolved submodel binding metadata used by API responses and update targeting."""

    submodel_id: str | None
    id_short: str | None
    semantic_id: str | None
    normalized_semantic_id: str | None
    template_key: str | None
    binding_source: BindingSource
    idta_version: str | None
    resolved_version: str | None
    support_status: str | None
    refresh_enabled: bool | None


def normalize_semantic_id(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().rstrip("/").lower()
    return normalized or None


def extract_semantic_id(item: dict[str, Any]) -> str | None:
    semantic_id = item.get("semanticId")
    if not isinstance(semantic_id, dict):
        return None
    keys = semantic_id.get("keys")
    if not isinstance(keys, list) or not keys:
        return None
    first = keys[0] if isinstance(keys[0], dict) else {}
    value = first.get("value")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def resolve_submodel_bindings(
    *,
    aas_env_json: dict[str, Any] | None,
    templates: list[Any],
    template_provenance: dict[str, Any] | None = None,
) -> list[ResolvedSubmodelBinding]:
    """Resolve template bindings for all submodels in an AAS environment."""
    submodels = aas_env_json.get("submodels", []) if isinstance(aas_env_json, dict) else []
    if not isinstance(submodels, list) or not submodels:
        return []

    template_by_key: dict[str, Any] = {}
    semantic_to_template: dict[str, str] = {}
    for template in templates:
        template_key = _template_attr(template, "template_key")
        if not template_key:
            continue
        template_by_key[template_key] = template
        normalized_semantic = normalize_semantic_id(_template_attr(template, "semantic_id"))
        if normalized_semantic:
            semantic_to_template[normalized_semantic] = template_key

    provenance_semantic_to_template: dict[str, str] = {}
    provenance = template_provenance if isinstance(template_provenance, dict) else {}
    for provenance_key, meta in provenance.items():
        if not isinstance(meta, dict):
            continue
        normalized_semantic = normalize_semantic_id(_dict_str(meta, "semantic_id"))
        if normalized_semantic:
            provenance_semantic_to_template[normalized_semantic] = provenance_key

    alias_to_template = _load_alias_map()
    available_template_keys = set(template_by_key) | set(provenance.keys())

    bindings: list[ResolvedSubmodelBinding] = []
    for submodel in submodels:
        if not isinstance(submodel, dict):
            continue
        semantic_id = extract_semantic_id(submodel)
        normalized_semantic = normalize_semantic_id(semantic_id)
        id_short = _dict_str(submodel, "idShort")
        submodel_id = _dict_str(submodel, "id")

        bound_template_key: str | None = None
        binding_source: BindingSource = "unresolved"

        if normalized_semantic and normalized_semantic in semantic_to_template:
            bound_template_key = semantic_to_template[normalized_semantic]
            binding_source = "semantic_exact"
        elif normalized_semantic and normalized_semantic in alias_to_template:
            candidate = alias_to_template[normalized_semantic]
            if candidate in available_template_keys:
                bound_template_key = candidate
                binding_source = "semantic_alias"
        elif normalized_semantic and normalized_semantic in provenance_semantic_to_template:
            bound_template_key = provenance_semantic_to_template[normalized_semantic]
            binding_source = "provenance"
        elif id_short:
            fallback_key = _kebab_case(id_short)
            if fallback_key in available_template_keys:
                bound_template_key = fallback_key
                binding_source = "id_short"

        template_obj = template_by_key.get(bound_template_key) if bound_template_key else None
        provenance_meta = provenance.get(bound_template_key, {}) if bound_template_key else {}
        if not isinstance(provenance_meta, dict):
            provenance_meta = {}

        idta_version = (
            _template_attr(template_obj, "idta_version")
            if template_obj is not None
            else _dict_str(provenance_meta, "idta_version")
        )
        resolved_version = (
            _template_attr(template_obj, "resolved_version")
            if template_obj is not None
            else _dict_str(provenance_meta, "resolved_version")
        )

        support_status = (
            get_template_support_status(bound_template_key) if bound_template_key else None
        )
        refresh_enabled = (
            is_template_refresh_enabled(bound_template_key) if bound_template_key else None
        )

        bindings.append(
            ResolvedSubmodelBinding(
                submodel_id=submodel_id,
                id_short=id_short,
                semantic_id=semantic_id,
                normalized_semantic_id=normalized_semantic,
                template_key=bound_template_key,
                binding_source=binding_source,
                idta_version=idta_version,
                resolved_version=resolved_version,
                support_status=support_status,
                refresh_enabled=refresh_enabled,
            )
        )

    return bindings


def _template_attr(template: Any, key: str) -> str | None:
    if template is None:
        return None
    if isinstance(template, dict):
        return _dict_str(template, key)
    value = getattr(template, key, None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _dict_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _kebab_case(value: str) -> str:
    source = value.strip()
    output: list[str] = []
    for index, char in enumerate(source):
        if char.isupper() and index > 0 and source[index - 1].isalnum():
            output.append("-")
        if char.isalnum():
            output.append(char.lower())
        elif char in {"_", " ", "."}:
            output.append("-")
    normalized = "".join(output)
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized.strip("-")


def _load_alias_map() -> dict[str, str]:
    registry = load_semantic_registry()
    aliases = registry.get("legacy_semantic_id_aliases", {})
    if not isinstance(aliases, dict):
        return {}
    normalized: dict[str, str] = {}
    for semantic_id, template_key in aliases.items():
        if not isinstance(semantic_id, str) or not isinstance(template_key, str):
            continue
        normalized_semantic = normalize_semantic_id(semantic_id)
        if normalized_semantic:
            normalized[normalized_semantic] = template_key
    return normalized
