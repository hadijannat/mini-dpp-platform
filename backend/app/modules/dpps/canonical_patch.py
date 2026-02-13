"""Deterministic canonical patch engine for AAS submodel mutations.

The engine updates only mutable value surfaces and preserves untouched
metadata (qualifiers, semantic IDs, embedded specs, extensions) verbatim.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from app.modules.dpps.idshort_factory import generate_next_id_short, validate_id_short_policy


@dataclass(frozen=True)
class CanonicalPatchResult:
    """Patch execution result."""

    aas_env_json: dict[str, Any]
    applied_operations: int


@dataclass(frozen=True)
class _ResolvedPath:
    element: dict[str, Any]
    parent_list: list[dict[str, Any]] | None
    parent_element: dict[str, Any] | None
    path_segments: list[str]


def apply_canonical_patch(
    *,
    aas_env_json: dict[str, Any],
    submodel_id: str,
    operations: list[dict[str, Any]],
    contract: dict[str, Any] | None,
    strict: bool = True,
) -> CanonicalPatchResult:
    """Apply deterministic patch operations to one submodel in an AAS environment."""
    cloned = json.loads(json.dumps(aas_env_json))
    submodel = _find_submodel(cloned, submodel_id)
    if submodel is None:
        raise ValueError(f"submodel_id '{submodel_id}' not found in AAS environment")

    contract_index = _build_contract_index(contract)

    applied = 0
    for operation in operations:
        op = str(operation.get("op") or "").strip()
        path = str(operation.get("path") or "").strip()
        if not op:
            raise ValueError("Patch operation is missing 'op'")
        if not path:
            raise ValueError(f"Patch operation '{op}' is missing 'path'")
        path_segments = _split_path(path)
        if not path_segments:
            raise ValueError(f"Patch operation '{op}' has invalid path '{path}'")

        if op in {"set_value", "set_multilang", "set_file_ref"}:
            resolved = _resolve_element_path(submodel, path_segments)
            contract_node = _resolve_contract_node(contract_index, path_segments, strict=strict)
            _assert_mutable(contract_node, op=op, path=path)
            if op == "set_value":
                _apply_set_value(resolved.element, operation.get("value"))
            elif op == "set_multilang":
                _apply_set_multilang(resolved.element, operation.get("value"))
            else:
                _apply_set_file_ref(resolved.element, operation.get("value"))
            applied += 1
            continue

        if op in {"add_list_item", "remove_list_item"}:
            resolved = _resolve_element_path(submodel, path_segments)
            model_type = _resolve_model_type(resolved.element)
            if model_type != "SubmodelElementList":
                raise ValueError(
                    f"Patch operation '{op}' requires SubmodelElementList at path '{path}', "
                    f"found '{model_type}'"
                )
            contract_node = _resolve_contract_node(contract_index, path_segments, strict=strict)
            _assert_mutable(contract_node, op=op, path=path)
            _assert_list_cardinality_precondition(
                contract_node=contract_node,
                current_items=_list_items(resolved.element),
                op=op,
            )
            if op == "add_list_item":
                _apply_add_list_item(
                    list_element=resolved.element,
                    payload=operation.get("value"),
                    contract_node=contract_node,
                )
            else:
                _apply_remove_list_item(
                    list_element=resolved.element,
                    index=operation.get("index"),
                    contract_node=contract_node,
                )
            applied += 1
            continue

        raise ValueError(f"Unsupported patch operation '{op}'")

    return CanonicalPatchResult(aas_env_json=cloned, applied_operations=applied)


def _split_path(path: str) -> list[str]:
    return [segment.strip() for segment in path.split("/") if segment.strip()]


def _find_submodel(aas_env_json: dict[str, Any], submodel_id: str) -> dict[str, Any] | None:
    submodels = aas_env_json.get("submodels")
    if not isinstance(submodels, list):
        return None
    for item in submodels:
        if not isinstance(item, dict):
            continue
        if str(item.get("id")) == submodel_id:
            return item
    return None


def _resolve_model_type(element: dict[str, Any]) -> str:
    raw = element.get("modelType")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        name = raw.get("name")
        return str(name) if name else ""
    return ""


def _child_elements(element: dict[str, Any]) -> list[dict[str, Any]] | None:
    model_type = _resolve_model_type(element)
    if model_type == "SubmodelElementCollection":
        value = element.get("value")
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
    if model_type == "Entity":
        for key in ("statements", "statement"):
            value = element.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []
    if model_type == "AnnotatedRelationshipElement":
        for key in ("annotations", "annotation"):
            value = element.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []
    return None


def _list_items(element: dict[str, Any]) -> list[dict[str, Any]]:
    value = element.get("value")
    if not isinstance(value, list):
        value = []
        element["value"] = value
    return [item for item in value if isinstance(item, dict)]


def _resolve_element_path(submodel: dict[str, Any], path_segments: list[str]) -> _ResolvedPath:
    root_elements = submodel.get("submodelElements")
    if not isinstance(root_elements, list):
        raise ValueError("Submodel has no submodelElements array")
    current_list = [item for item in root_elements if isinstance(item, dict)]
    current_element: dict[str, Any] | None = None
    parent_element: dict[str, Any] | None = None
    parent_list: list[dict[str, Any]] | None = current_list

    for idx, segment in enumerate(path_segments):
        if current_element is None:
            current_element = _find_child_by_id_short(current_list, segment)
            if current_element is None:
                raise ValueError(
                    f"Path not found at segment '{segment}' "
                    f"(resolved='{ '/'.join(path_segments[:idx]) }')"
                )
            continue

        model_type = _resolve_model_type(current_element)
        if model_type == "SubmodelElementList":
            if _is_index_segment(segment):
                items = _list_items(current_element)
                item_index = int(segment)
                if item_index < 0 or item_index >= len(items):
                    raise ValueError(
                        f"List index {item_index} out of bounds at "
                        f"'{ '/'.join(path_segments[:idx + 1]) }'"
                    )
                parent_element = current_element
                parent_list = items
                current_element = items[item_index]
                continue
            raise ValueError(
                f"List path requires numeric index after '{ '/'.join(path_segments[:idx]) }'"
            )

        children = _child_elements(current_element)
        if children is None:
            raise ValueError(
                f"Path segment '{segment}' targets a leaf element at "
                f"'{ '/'.join(path_segments[:idx]) }'"
            )
        next_element = _find_child_by_id_short(children, segment)
        if next_element is None:
            raise ValueError(
                f"Path not found at segment '{segment}' "
                f"(resolved='{ '/'.join(path_segments[:idx]) }')"
            )
        parent_element = current_element
        parent_list = children
        current_element = next_element

    if current_element is None:
        raise ValueError("Resolved path does not reference an element")
    return _ResolvedPath(
        element=current_element,
        parent_list=parent_list,
        parent_element=parent_element,
        path_segments=path_segments,
    )


def _find_child_by_id_short(elements: list[dict[str, Any]], id_short: str) -> dict[str, Any] | None:
    for item in elements:
        if str(item.get("idShort")) == id_short:
            return item
    return None


def _is_index_segment(segment: str) -> bool:
    return segment.isdigit()


def _normalize_contract_path(path_segments: list[str]) -> str:
    normalized = ["[]" if _is_index_segment(segment) else segment for segment in path_segments]
    return "/".join(normalized)


def _build_contract_index(contract: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(contract, dict):
        return {}
    definition = contract.get("definition")
    if not isinstance(definition, dict):
        definition = contract
    submodel = definition.get("submodel")
    if not isinstance(submodel, dict):
        return {}
    elements = submodel.get("elements")
    if not isinstance(elements, list):
        return {}

    index: dict[str, dict[str, Any]] = {}

    def visit(node: dict[str, Any], path: list[str]) -> None:
        id_short = node.get("idShort")
        if isinstance(id_short, str) and id_short:
            node_path = [*path, id_short]
            key = "/".join(node_path)
            index[key] = node
        else:
            node_path = path

        model_type = node.get("modelType")
        if model_type == "SubmodelElementCollection":
            for child in _as_node_list(node.get("children")):
                visit(child, node_path)
        elif model_type == "SubmodelElementList":
            item = node.get("items")
            if isinstance(item, dict):
                visit(item, [*node_path, "[]"])
        elif model_type == "Entity":
            for statement in _as_node_list(node.get("statements")):
                visit(statement, [*node_path, "statements"])
        elif model_type == "AnnotatedRelationshipElement":
            for annotation in _as_node_list(node.get("annotations")):
                visit(annotation, [*node_path, "annotations"])

    for element in _as_node_list(elements):
        visit(element, [])
    return index


def _as_node_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _resolve_contract_node(
    contract_index: dict[str, dict[str, Any]],
    path_segments: list[str],
    *,
    strict: bool,
) -> dict[str, Any] | None:
    if not contract_index:
        return None
    key = _normalize_contract_path(path_segments)
    node = contract_index.get(key)
    if node is None and strict:
        raise ValueError(f"Patch path '{'/'.join(path_segments)}' is not present in strict contract")
    return node


def _assert_mutable(contract_node: dict[str, Any] | None, *, op: str, path: str) -> None:
    if not contract_node:
        return
    smt = contract_node.get("smt")
    if not isinstance(smt, dict):
        return
    access_mode = str(smt.get("access_mode") or "").strip().lower()
    if access_mode in {"readonly", "read-only", "read_only"}:
        raise ValueError(f"Operation '{op}' is blocked by SMT/AccessMode=ReadOnly at '{path}'")


def _apply_set_value(element: dict[str, Any], value: Any) -> None:
    model_type = _resolve_model_type(element)
    if model_type == "Property":
        element["value"] = value
        return
    if model_type == "Range":
        if not isinstance(value, dict):
            raise ValueError("set_value for Range requires object with min/max")
        element["min"] = value.get("min")
        element["max"] = value.get("max")
        return
    raise ValueError(f"set_value is not supported for modelType '{model_type}'")


def _apply_set_multilang(element: dict[str, Any], value: Any) -> None:
    model_type = _resolve_model_type(element)
    if model_type != "MultiLanguageProperty":
        raise ValueError(f"set_multilang requires MultiLanguageProperty, found '{model_type}'")
    if not isinstance(value, dict):
        raise ValueError("set_multilang requires value object of language->text")
    entries = [
        {"language": language, "text": str(text)}
        for language, text in sorted(value.items(), key=lambda item: str(item[0]))
        if str(language).strip()
    ]
    element["value"] = entries


def _apply_set_file_ref(element: dict[str, Any], value: Any) -> None:
    model_type = _resolve_model_type(element)
    if model_type not in {"File", "Blob"}:
        raise ValueError(f"set_file_ref requires File/Blob, found '{model_type}'")
    if not isinstance(value, dict):
        raise ValueError("set_file_ref requires object with contentType and url/value")
    content_type = value.get("contentType")
    if content_type is not None:
        element["contentType"] = content_type
    if "url" in value:
        element["value"] = value.get("url")
    elif "value" in value:
        element["value"] = value.get("value")


def _assert_list_cardinality_precondition(
    *,
    contract_node: dict[str, Any] | None,
    current_items: list[dict[str, Any]],
    op: str,
) -> None:
    if not contract_node:
        return
    smt = contract_node.get("smt")
    if not isinstance(smt, dict):
        return
    cardinality = str(smt.get("cardinality") or "").strip() or "One"
    item_count = len(current_items)
    if op == "add_list_item" and cardinality in {"One", "ZeroToOne"}:
        raise ValueError(f"Cardinality '{cardinality}' blocks add_list_item")
    if op == "remove_list_item" and cardinality in {"One", "OneToMany"} and item_count <= 1:
        raise ValueError(f"Cardinality '{cardinality}' requires at least one list item")


def _apply_add_list_item(
    *,
    list_element: dict[str, Any],
    payload: Any,
    contract_node: dict[str, Any] | None,
) -> None:
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("add_list_item requires object payload")

    items = _list_items(list_element)
    template_item = copy.deepcopy(items[0]) if items else _build_item_from_contract(contract_node)
    if template_item is None:
        raise ValueError("Cannot add list item: missing template item structure")

    _apply_payload_to_element(template_item, payload)
    existing_id_shorts = [
        str(item.get("idShort"))
        for item in items
        if isinstance(item.get("idShort"), str) and str(item.get("idShort")).strip()
    ]
    template_pattern_id_short = _contract_item_id_short(contract_node) or str(
        template_item.get("idShort") or "Item"
    )
    if "idShort" in payload and payload.get("idShort"):
        candidate = str(payload["idShort"]).strip()
    else:
        candidate = generate_next_id_short(template_pattern_id_short, existing_id_shorts)

    policy = _extract_list_item_idshort_policy(contract_node)
    validate_id_short_policy(
        candidate=candidate,
        allowed_id_shorts=policy.get("allowed_id_short"),
        naming_regex=policy.get("naming"),
    )
    if candidate in set(existing_id_shorts):
        raise ValueError(f"Generated duplicate idShort '{candidate}' for list item")

    # Preserve explicit idShort=None templates by setting idShort only when policy allows.
    if payload.get("idShort") is not None or template_item.get("idShort") is not None:
        template_item["idShort"] = candidate

    value = list_element.get("value")
    if not isinstance(value, list):
        value = []
        list_element["value"] = value
    value.append(template_item)


def _apply_remove_list_item(
    *,
    list_element: dict[str, Any],
    index: Any,
    contract_node: dict[str, Any] | None,
) -> None:
    if not isinstance(index, int):
        raise ValueError("remove_list_item requires integer 'index'")
    value = list_element.get("value")
    if not isinstance(value, list):
        raise ValueError("List element has no value array")
    if index < 0 or index >= len(value):
        raise ValueError(f"remove_list_item index {index} out of bounds")
    cardinality = ""
    if isinstance(contract_node, dict):
        smt = contract_node.get("smt")
        if isinstance(smt, dict):
            cardinality = str(smt.get("cardinality") or "").strip()
    if cardinality in {"One", "OneToMany"} and len(value) <= 1:
        raise ValueError(f"Cardinality '{cardinality}' requires at least one list item")
    del value[index]


def _extract_list_item_idshort_policy(contract_node: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(contract_node, dict):
        return {"allowed_id_short": None, "naming": None}
    smt = contract_node.get("smt")
    if not isinstance(smt, dict):
        return {"allowed_id_short": None, "naming": None}
    allowed = smt.get("allowed_id_short")
    allowed_list = (
        [str(item) for item in allowed if str(item).strip()]
        if isinstance(allowed, list)
        else None
    )
    naming = smt.get("naming")
    return {"allowed_id_short": allowed_list, "naming": str(naming) if naming else None}


def _contract_item_id_short(contract_node: dict[str, Any] | None) -> str | None:
    if not isinstance(contract_node, dict):
        return None
    item = contract_node.get("items")
    if not isinstance(item, dict):
        return None
    id_short = item.get("idShort")
    if isinstance(id_short, str) and id_short.strip():
        return id_short.strip()
    return None


def _build_item_from_contract(contract_node: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(contract_node, dict):
        return None
    item = contract_node.get("items")
    if not isinstance(item, dict):
        return None
    return _build_element_from_definition(item)


def _build_element_from_definition(node: dict[str, Any]) -> dict[str, Any]:
    model_type = str(node.get("modelType") or "Property")
    element: dict[str, Any] = {
        "modelType": {"name": model_type},
    }
    id_short = node.get("idShort")
    if isinstance(id_short, str):
        element["idShort"] = id_short

    if model_type == "Property":
        element["value"] = None
        if node.get("valueType"):
            element["valueType"] = node["valueType"]
        return element
    if model_type == "MultiLanguageProperty":
        element["value"] = []
        return element
    if model_type == "Range":
        element["min"] = None
        element["max"] = None
        if node.get("valueType"):
            element["valueType"] = node["valueType"]
        return element
    if model_type == "File":
        element["contentType"] = node.get("contentType") or ""
        element["value"] = None
        return element
    if model_type == "Blob":
        element["contentType"] = node.get("contentType") or ""
        element["value"] = None
        return element
    if model_type == "SubmodelElementCollection":
        children = [_build_element_from_definition(child) for child in _as_node_list(node.get("children"))]
        element["value"] = children
        return element
    if model_type == "SubmodelElementList":
        items = node.get("items")
        element["value"] = [_build_element_from_definition(items)] if isinstance(items, dict) else []
        return element
    return element


def _apply_payload_to_element(element: dict[str, Any], payload: dict[str, Any]) -> None:
    model_type = _resolve_model_type(element)
    if model_type == "Property":
        if "value" in payload:
            element["value"] = payload["value"]
        elif payload:
            # Legacy payloads send scalar directly.
            element["value"] = payload
        return
    if model_type == "MultiLanguageProperty":
        value = payload.get("value", payload)
        if isinstance(value, dict):
            element["value"] = [
                {"language": lang, "text": str(text)}
                for lang, text in sorted(value.items(), key=lambda item: str(item[0]))
                if str(lang).strip()
            ]
        return
    if model_type == "Range":
        value = payload.get("value", payload)
        if isinstance(value, dict):
            element["min"] = value.get("min")
            element["max"] = value.get("max")
        return
    if model_type in {"File", "Blob"}:
        value = payload.get("value", payload)
        if isinstance(value, dict):
            if "contentType" in value:
                element["contentType"] = value.get("contentType")
            if "url" in value:
                element["value"] = value.get("url")
            elif "value" in value:
                element["value"] = value.get("value")
        return
    if model_type == "SubmodelElementCollection":
        children = _child_elements(element) or []
        for child in children:
            child_id_short = child.get("idShort")
            if not isinstance(child_id_short, str):
                continue
            if child_id_short in payload and isinstance(payload[child_id_short], dict):
                _apply_payload_to_element(child, payload[child_id_short])
            elif child_id_short in payload:
                _apply_payload_to_element(child, {"value": payload[child_id_short]})
        return
