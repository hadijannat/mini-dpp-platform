"""Shared AAS/BaSyx utilities for reference handling, model operations, and traversal."""

from app.modules.aas.model_utils import (
    clear_parent,
    clone_identifiable,
    enum_to_str,
    iterable_attr,
    lang_string_set_to_dict,
    walk_submodel_deep,
)
from app.modules.aas.references import (
    extract_semantic_id_str,
    reference_from_dict,
    reference_to_dict,
    reference_to_str,
)

__all__ = [
    "clear_parent",
    "clone_identifiable",
    "enum_to_str",
    "extract_semantic_id_str",
    "iterable_attr",
    "lang_string_set_to_dict",
    "reference_from_dict",
    "reference_to_dict",
    "reference_to_str",
    "walk_submodel_deep",
]
