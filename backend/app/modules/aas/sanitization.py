"""AAS environment sanitization helpers."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SanitizationStats:
    """Counters emitted by list-item idShort sanitization."""

    lists_scanned: int = 0
    items_scanned: int = 0
    idshort_removed: int = 0
    paths_changed: list[str] = field(default_factory=list)


def sanitize_submodel_list_item_id_shorts(
    aas_env: dict[str, Any],
) -> tuple[dict[str, Any], SanitizationStats]:
    """Remove illegal ``idShort`` fields from ``SubmodelElementList`` items.

    AAS constraint AASd-120 requires that direct children of
    ``SubmodelElementList`` do not carry ``idShort``.
    """

    sanitized = copy.deepcopy(aas_env)
    stats = SanitizationStats()
    changed_paths: set[str] = set()

    def resolve_model_type(model_type: Any) -> str:
        if isinstance(model_type, str):
            return model_type
        if isinstance(model_type, dict):
            name = model_type.get("name")
            if isinstance(name, str):
                return name
        return ""

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            model_type = resolve_model_type(node.get("modelType"))
            if model_type == "SubmodelElementList":
                stats.lists_scanned += 1
                value = node.get("value")
                if isinstance(value, list):
                    for index, item in enumerate(value):
                        stats.items_scanned += 1
                        if isinstance(item, dict) and "idShort" in item:
                            item.pop("idShort", None)
                            stats.idshort_removed += 1
                            changed_paths.add(f"{path}.value[{index}]")

            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    walk(value, f"{path}.{key}" if path else key)
            return

        if isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}[{index}]")

    walk(sanitized, "")
    stats.paths_changed = sorted(changed_paths)
    return sanitized, stats

