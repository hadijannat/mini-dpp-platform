"""Consolidated BaSyx model utility functions.

Extracted from duplicate implementations across definition.py and basyx_builder.py.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from typing import Any

from basyx.aas import model


def enum_to_str(value: Any) -> str | None:
    """Convert a BaSyx enum (or type) to its string representation."""
    if value is None:
        return None
    if isinstance(value, type):
        return str(value)
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def lang_string_set_to_dict(value: Any) -> dict[str, str]:
    """Convert a BaSyx LangStringSet (or similar iterable) to ``{language: text}``.

    Handles BaSyx ``MultiLanguageNameType`` / ``LangStringSet`` (dict-like with
    ``.items()``), older tuple-of-objects formats (entries with ``.language`` /
    ``.text``), and plain strings.
    """
    if not value:
        return {}
    if isinstance(value, str):
        return {"und": value}
    # BaSyx LangStringSet is dict-like with .items()
    if hasattr(value, "items"):
        return {str(k): str(v) for k, v in value.items()}
    # Single entry object with .language / .text
    if hasattr(value, "language") and hasattr(value, "text"):
        language = getattr(value, "language", None)
        text = getattr(value, "text", None)
        if language is not None and text is not None:
            return {str(language): str(text)}
    # Iterable of entry objects
    result: dict[str, str] = {}
    for entry in value:
        language = getattr(entry, "language", None)
        text = getattr(entry, "text", None)
        if language is not None and text is not None:
            result[str(language)] = str(text)
    return result


def iterable_attr(obj: Any, *names: str) -> list[Any]:
    """Extract the first non-None iterable attribute from *obj* by trying *names* in order.

    Returns a sorted list of elements. Handles BaSyx's NamespaceSet (dict-like)
    and plain list/tuple containers.
    """
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            if isinstance(value, (list, tuple)):
                return list(value)
            items = list(value.values()) if isinstance(value, dict) else list(value)
            items.sort(key=_element_sort_key)
            return items
    return []


def clear_parent(element: model.SubmodelElement) -> None:
    """Recursively clear the ``parent`` attribute on *element* and all children.

    Uses :func:`walk_submodel_deep` for complete traversal including Entity
    statements, AnnotatedRelationshipElement annotations, and Operation variables.
    """
    if hasattr(element, "parent"):
        element.parent = None
    for child in walk_submodel_deep(element):
        if hasattr(child, "parent"):
            child.parent = None


def clone_identifiable(identifiable: model.Identifiable) -> model.Identifiable:
    """Deep-copy an Identifiable and clear its parent reference."""
    cloned = copy.deepcopy(identifiable)
    if hasattr(cloned, "parent"):
        cloned.parent = None
    return cloned


def walk_submodel_deep(
    root: model.Submodel | model.SubmodelElement,
) -> Iterator[model.SubmodelElement]:
    """Recursively yield all SubmodelElements under *root* in pre-order.

    Extends BaSyx's ``walk_submodel()`` to also traverse:
    - ``Entity.statement`` children
    - ``AnnotatedRelationshipElement.annotation`` children
    - ``Operation`` input/output/in_output variables
    """
    if isinstance(root, model.Submodel):
        elements: Any = root.submodel_element
    elif isinstance(root, (model.SubmodelElementCollection, model.SubmodelElementList)):
        elements = root.value
    elif isinstance(root, model.Entity):
        elements = root.statement
    elif isinstance(root, model.AnnotatedRelationshipElement):
        elements = root.annotation
    elif isinstance(root, model.Operation):
        elements = []
        for var_kind in ("input_variable", "output_variable", "in_output_variable"):
            variables = getattr(root, var_kind, None)
            if variables:
                elements.extend(variables)
    else:
        return

    for element in elements:
        yield element
        yield from walk_submodel_deep(element)


def _element_sort_key(element: Any) -> tuple[str, str]:
    """Stable sort key for BaSyx elements — by id_short, then id, then repr."""
    id_short = getattr(element, "id_short", None)
    if id_short:
        return ("0", str(id_short))
    identifier = getattr(element, "id", None)
    if identifier:
        return ("1", str(identifier))
    return ("2", str(element))
